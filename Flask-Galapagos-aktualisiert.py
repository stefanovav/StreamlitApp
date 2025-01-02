import streamlit as st
import plotly.graph_objects as go
import requests
from flask import Flask
from specklepy.api import operations
from specklepy.api.client import SpeckleClient
from specklepy.transports.server import ServerTransport
from specklepy.api.credentials import get_account_from_token
from specklepy.objects import Base
import os
import copy
import streamlit.components.v1 as components
import specklepy
# import compute_rhino3d.Util
# import compute_rhino3d.Grasshopper as gh
# from compute_rhino3d.Grasshopper import DataTree
# import compute_rhino3d as compute
import json
# from compute_rhino3d.Util import url as rhino_url
# from compute_rhino3d.Grasshopper import EvaluateDefinition



# Instantiate material mappings
#MATERIALS_MAPPING1 = SteelS355()
#MATERIALS_MAPPING2 = SteelS235()

# compute_rhino3d.Util.url = r'http://localhost:6500/'.encode('utf-8')




# Speckle server configuration
HOST = "app.speckle.systems"
STREAM_ID = "f132a9844d"
COMMIT_FILE_PATH = "CommitID.txt"  # Update with your file path

def get_latest_commit_id(file_path):
    """Retrieve the latest commit ID from a file."""
    try:
        with open(file_path, 'r') as f:
            commit_id = f.read().strip()
        return commit_id
    except FileNotFoundError:
        st.error("Commit ID file not found.")
        return None

# def find_and_update_mesh(members_data, area, thickness):
#     """
#     Finds the first Mesh object in the members_data, updates its area and thickness,
#     and stops further processing once found.
#
#     Args:
#         members_data: The `Members` object to process.
#         area (float): The area to set.
#         thickness (float): The thickness to set.
#
#     Returns:
#         (bool, object): A tuple where the first value is True if a Mesh object was found
#                         and updated, and the second value is the updated `members_data`.
#     """
#     branch_keys = [key for key in dir(members_data) if not key.startswith("_")]
#     mesh_found = False  # Flag to stop further processing once a mesh is found
#
#     for branch_key in branch_keys:
#         try:
#             branch_value = getattr(members_data, branch_key, None)
#
#             # Ensure the branch is a list
#             if isinstance(branch_value, list) and len(branch_value) > 0:
#                 for index, element in enumerate(branch_value):
#                     member_obj = getattr(element, "Member", None)
#                     if member_obj and isinstance(member_obj, Base) and member_obj.speckle_type == "Objects.Geometry.Mesh":
#                         # Update Mesh attributes
#                         if hasattr(member_obj, 'area'):
#                             setattr(member_obj, 'area', area)
#                         else:
#                             member_obj.area = area  # Dynamically add if needed
#
#                         if hasattr(member_obj, 'thickness'):
#                             setattr(member_obj, 'thickness', thickness)
#                         else:
#                             member_obj.thickness = thickness  # Dynamically add if needed
#
#                         # Stop further processing
#                         mesh_found = True
#                         break  # Exit inner loop
#                 if mesh_found:
#                     break  # Exit outer loop
#         except Exception as e:
#             # Log or handle errors while processing branches
#             print(f"Error processing branch '{branch_key}': {e}")
#
#     # Return the result
#     return mesh_found, members_data

def find_and_update_mesh(members_data, area, thickness):
    branch_keys = [key for key in dir(members_data) if key.startswith("@{")]

    updated_members_data = {}

    for branch_key in branch_keys:
        branch_value = getattr(members_data, branch_key, None)

        if isinstance(branch_value, list):
            updated_branch = []
            for element in branch_value:
                member_obj = getattr(element, "Member", None)
                if member_obj and member_obj.speckle_type == "Objects.Geometry.Mesh":
                    member_obj.area = area
                    member_obj.thickness = thickness
                updated_branch.append(element)

            # Store the updated branch back in the new structure
            updated_members_data[branch_key] = updated_branch

    return updated_members_data


def send_data_to_speckle(area, thickness, stream_id, speckle_token, res):
    client = SpeckleClient(host=HOST)
    account = get_account_from_token(speckle_token, HOST)
    client.authenticate_with_account(account)

    # Access Members data
    members_data = getattr(res, "Members", None)
    if members_data is None:
        st.error("'Members' not found in the response object.")
        return

    # Use find_and_update_mesh to update the data
    updated_members_data = find_and_update_mesh(members_data, area, thickness)

    # Reassign the updated structure back to `res.Members`
    for branch_key, updated_branch in updated_members_data.items():
        setattr(members_data, branch_key, updated_branch)

    setattr(res, "Members", members_data)

    # Send updated data back to Speckle


    try:
        transport = ServerTransport(client=client, stream_id=stream_id)
        obj_id = operations.send(res, [transport])

        # Create a new commit
        new_commit_id = client.commit.create(
            stream_id=stream_id,
            object_id=obj_id,
            branch_name="main",
            message=f"Updated area and thickness: area={area}, thickness={thickness}"
        )
        return new_commit_id
    except Exception as e:
        st.error(f"Failed to create a new commit: {e}")
        return None


@st.cache_data
def fetch_data_from_speckle(stream_id, commit_id, speckle_token):
    """Fetch data from the Speckle server."""
    client = SpeckleClient(host=HOST)

    if not speckle_token:
        st.error("Speckle token is not set. Please enter the SPECKLE_TOKEN.")
        return None, None

    try:
        account = get_account_from_token(speckle_token, HOST)
        client.authenticate_with_account(account)
        st.success("Successfully authenticated with Speckle.")
    except Exception as e:
        st.error(f"Failed to authenticate with Speckle: {e}")
        return None, None

    try:
        stream = client.stream.get(stream_id)
        commit = client.commit.get(stream_id, commit_id)
        return stream, commit
    except Exception as e:
        st.error(f"Failed to fetch stream or commit: {e}")
        return None, None


# def parse_dimensions_from_commit(client, stream_id, commit_id, speckle_token):
#     """Parse dimensions from the commit object."""
#     try:
#         # Authenticate client if necessary
#         account = get_account_from_token(speckle_token, HOST)
#         client.authenticate_with_account(account)
#
#         # Fetch the commit object using the commit ID
#         commit = client.commit.get(stream_id, commit_id)
#         referenced_object_id = commit.referencedObject
#         transport = ServerTransport(client=client, stream_id=stream_id)
#         res = operations.receive(referenced_object_id, transport)
#
#         st.write("Commit Data Received:", res)
#
#         # Step 1: Access the 'Members' data
#         members_data = getattr(res, "Members", None)
#         if members_data:
#             st.write("Members Data:", members_data)
#
#             # Step 2: Access the @{0;0} branch
#             sublist0 = members_data["@{0;0}"]
#             if sublist0 and isinstance(sublist0, list) and len(sublist0) > 0:
#                 st.write("Sublist0 Data:", sublist0)
#
#                 # Step 3: Access the first element in sublist0 (directly an object)
#                 member_element = sublist0[0]
#
#                 # Attempt to access '@Member' or 'Member' directly
#                 member_obj = None
#                 if hasattr(member_element, "@Member"):
#                     member_obj = getattr(member_element, "@Member", None)
#                 elif hasattr(member_element, "Member"):
#                     member_obj = getattr(member_element, "Member", None)
#                 elif isinstance(member_element, dict) and "Member" in member_element:
#                     member_obj = member_element["Member"]
#
#                 if member_obj:
#                     st.write("Member object found:", member_obj)
#
#                     # Check if member_obj has area and thickness attributes
#                     if hasattr(member_obj, 'area'):
#                         fetched_area = member_obj.area
#                     if hasattr(member_obj, 'thickness'):
#                         fetched_thickness = member_obj.thickness
#                         return fetched_area, fetched_thickness
#                     else:
#                         st.error("The 'Member' object does not have an 'area' or 'thickness' attribute.")
#                         return 0, 0
#         # Default return if dimensions not found
#         return 0, 0
#     except Exception as e:
#         st.error(f"Error parsing dimensions from commit: {e}")
#         return 0, 0


# def parse_and_display_data(client, stream_id, commit_id, speckle_token):
#     """Fetch and parse material data from the commit object and display it in a table."""
#     try:
#         # Authenticate client if necessary
#         account = get_account_from_token(speckle_token, HOST)
#         client.authenticate_with_account(account)
#
#         # Fetch the commit object using the commit ID
#         commit = client.commit.get(stream_id, commit_id)
#         referenced_object_id = commit.referencedObject
#         transport = ServerTransport(client=client, stream_id=stream_id)
#         res = operations.receive(referenced_object_id, transport)
#
#         # Getting data for the members of the commit in the list Members -> @0
#         moment_data = getattr(res, "Moment Value", None)
#
#         if moment_data:
#             sublist1 = getattr(moment_data, "@{0}", None)  # Retrieve the '@{0}' attribute
#
#             if isinstance(sublist1, list):  # Check if sublist1 is a list
#                 combined_data = [{'Moment Value': value} for value in sublist1]  # Create combined_data
#                 display_combined_table(combined_data)  # Directly display the table
#             else:
#                 print(f"Unexpected data type: {type(sublist1)}")  # For debugging
#
#         else:
#             st.error("No moment data found.")
#
#     except Exception as e:
#         st.error(f"Error parsing material data from commit: {e}")


def commit2viewer(stream_id, commit_id, speckle_token):
    """Embed Speckle viewer."""
    height = 600  # Default height for the viewer
    if commit_id:
        embed_src = f"https://speckle.xyz/embed?stream={stream_id}&commit={commit_id}&access_token={speckle_token}"
        st.write(f"Embed URL: {embed_src}")  # Debugging line to confirm embed URL
        components.iframe(embed_src, height=height, scrolling=True)
    else:
        st.error("Unable to display viewer: commit ID is not available.")


def transform_keys_to_integers(obj):
    """Recursively transform dictionary keys from '@{0}' to integers for display."""
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            try:
                new_key = int(k.strip('@{}'))
            except ValueError:
                new_key = k
            new_obj[new_key] = transform_keys_to_integers(v)
        return new_obj
    elif isinstance(obj, list):
        return [transform_keys_to_integers(item) for item in obj]
    else:
        return obj


def display_combined_table(combined_data):
    """Display the combined data in a Plotly table."""

    # Calculate the height dynamically based on the number of rows
    num_rows = len(combined_data)
    row_height = 30  # Adjust this value as needed
    table_height = num_rows * row_height

    header_values = list(combined_data[0].keys())
    cell_values = [list(col) for col in zip(*[list(row.values()) for row in combined_data])]

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=header_values,
            fill_color='paleturquoise',
            align='left',
            font=dict(size=16)  # Set header font size to 16
        ),
        cells=dict(
            values=cell_values,
            fill_color='#F5F5F5',
            align='left',
            font=dict(size=14)  # Set cell font size to 14
        )
    )])

    # Update the layout to adjust the height
    fig.update_layout(
        height=table_height,
        margin=dict(t=0, b=0, pad=0)
    )

    st.plotly_chart(fig)

# def send_to_grasshopper(gh_def_file_path, formatted_inputs):
#     """
#     Sends data to Grasshopper and retrieves the computation results.
#
#     Args:
#         gh_def_file_path (str): Path to the Grasshopper definition file.
#         formatted_inputs (list): Formatted inputs as required by Grasshopper.
#
#     Returns:
#         dict: Computation result from Grasshopper.
#     """
#     try:
#         # Call Grasshopper Compute API
#         output = gh.EvaluateDefinition(gh_def_file_path, formatted_inputs)
#
#         # Check if output contains errors
#         if "errors" in output and output["errors"]:
#             raise RuntimeError(f"Grasshopper returned errors: {output['errors']}")
#
#         return output
#     except Exception as e:
#         raise RuntimeError(f"Failed to communicate with Grasshopper: {e}")
# def compute_gh_with_params(gh_def_file_path, input_params):
#     compute_rhino3d.Util.url = r'http://localhost:6500/'
#
#     formatted_inputs = [
#         {
#             "ParamName": key,
#             "InnerTree": {
#                 "{0;0}": [
#                     {
#                         "type": value["type"],
#                         "data": value["data"]
#                     }
#                 ]
#             }
#         }
#         for key, value in input_params.items()
#     ]
#     #formatted_inputs = format_params(input_params)
#     try:
#         result = send_to_grasshopper(gh_def_file_path, formatted_inputs)
#         return result
#     except Exception as e:
#        raise RuntimeError(f"Grasshopper computation failed: {e}")


def main():
    global COMMIT_FILE_PATH
    new_commit_id = None  # Initialize new_commit_id before use

    st.title("Speckle Moment Values on a Concrete Shell")

    # Step 1: Get the latest commit ID from the file
    COMMIT_ID = get_latest_commit_id(COMMIT_FILE_PATH)
    if not COMMIT_ID:
        st.error("Failed to retrieve the latest commit ID.")
        return


    # Try to get the token from the environment first

    SPECKLE_TOKEN = os.getenv("SPECKLE_TOKEN")

    # Debugging: Check if the token is retrieved
    if SPECKLE_TOKEN:
        st.success("Speckle Token successfully retrieved from the environment.")
    else:
        st.warning("Speckle Token is not set in the environment.")
        st.info("Please set the 'SPECKLE_TOKEN' environment variable or provide it manually.")

    # Optional fallback for user input
    if not SPECKLE_TOKEN:
        user_input = st.text_input("Enter Speckle Token:", type="password")
        if user_input:
            SPECKLE_TOKEN = user_input
            st.success("Speckle Token set from user input.")
        else:
            st.error("Speckle Token is required to proceed.")
            st.stop()

    # Debugging output




    # Step 3: User inputs for area and thickness
    area = st.number_input("Enter area, [m²]:", min_value=1.0, step=0.1)
    thickness = st.number_input("Enter thickness, [cm]:", min_value=1.0, step=0.1)

    if st.button("Send Data to Speckle"):
        if SPECKLE_TOKEN:
            stream, commit = fetch_data_from_speckle(STREAM_ID, COMMIT_ID, SPECKLE_TOKEN)

            # gh_def_file_path = r'C:\Users\Denitsa\Documents\WebSite\22.Video\GHScript_Karamba3d_2d Structures.gh'
            # compute_rhino3d.Util.url = r'http://localhost:6500/'
            #
            # # Use the current values of area and thickness
            # input_params = {
            #     "Area": area,
            #     "Thickness":thickness,
            # }
            #
            # # Debugging: Print inputs being sent to Grasshopper
            # st.write("Sending to Grasshopper:", input_params)
            #
            # try:
            #     result = compute_rhino3d.Grasshopper.EvaluateDefinition(gh_def_file_path, input_params)
            #     st.write("Raw Grasshopper Result:", result)
            #
            #     try:
            #         # Directly treat result as MomentValues
            #         if isinstance(result, list):
            #             moment_values = [float(value) for value in result]
            #             st.write("Moment Values:", moment_values)
            #         else:
            #             st.error("Result is not a list. Unexpected format:", result)
            #     except Exception as e:
            #         st.error(f"Error processing MomentValues: {e}")



            #     else:
            #         st.error("Failed to retrieve 'MomentValues'. Check the Grasshopper definition.")
            #
            #
            # except Exception as e:
            #     st.error(f"Error processing data: {e}")

            client = SpeckleClient(host=HOST)
            account = get_account_from_token(SPECKLE_TOKEN, HOST)
            client.authenticate_with_account(account)

            transport = ServerTransport(client=client, stream_id=STREAM_ID)

            # Fetch and modify geometry data
            res = operations.receive(commit.referencedObject, transport)
            if res:
                new_commit_id = send_data_to_speckle(area, thickness, STREAM_ID, SPECKLE_TOKEN, res)
                if new_commit_id:
                    st.write("New commit ID:", new_commit_id)
                    st.write("Sent data: Area =", area, "Thickness =", thickness)
                else:
                    st.error("Failed to update and send data to Speckle.")
            else:
                st.error("Failed to receive geometry data from Speckle.")
        else:
            st.error("Please enter the Speckle token.")

    # Fetch data from Speckle server
    stream, commit = fetch_data_from_speckle(STREAM_ID, COMMIT_ID, SPECKLE_TOKEN)
    if not stream or not commit:
        st.error("Failed to fetch stream or commit. Please check your Speckle server setup.")
        return

    st.write("Stream Name:", stream.name)
    st.write("Commit Message:", commit.message)

    try:
        client = SpeckleClient(host=HOST)
        account = get_account_from_token(SPECKLE_TOKEN, HOST)
        client.authenticate_with_account(account)
        #st.write("Successfully authenticated with Speckle for sending data.")

        transport = ServerTransport(client=client, stream_id=STREAM_ID)
        res = operations.receive(commit.referencedObject, transport)

        if res:

            transformed_res = transform_keys_to_integers(copy.deepcopy(res))
            st.write("Transformed Data for Display:", transformed_res)

            members_data = getattr(res, "Members", None)
            if members_data is None:
                st.error("'Members' not found in the response object.")
                return

            updated_members_data = find_and_update_mesh(members_data, area, thickness)

            # Reassign the updated structure back to `res.Members`
            for branch_key, updated_branch in updated_members_data.items():
                setattr(members_data, branch_key, updated_branch)

            setattr(res, "Members", members_data)


            # Step 4: Re-assign the modified branch back into `members_data` to preserve the overall structure
    #         existing_members_data = getattr(res, "Members", {})
    #         existing_members_data["@{0;0}"] = sublist0  # Update the modified branch
    #         setattr(res, "Members", existing_members_data)

            obj_id = operations.send(res, [transport])

            if obj_id:
                st.write("Data successfully sent to Speckle. Object ID:", obj_id)
                latest_commits = client.commit.list(STREAM_ID)
                latest_commit = latest_commits[0] if latest_commits else None

                if latest_commit:
                    new_commit_id = latest_commit.id  # Assign new_commit_id here
                    st.write("Latest (updated) Commit ID:", new_commit_id)

                    commit2viewer(STREAM_ID, new_commit_id, SPECKLE_TOKEN)
                else:
                    st.error("No commits found in the stream.")
            else:
                st.error("Failed to send data to Speckle.")

            # fetched_area, fetched_thickness = parse_dimensions_from_commit(client, STREAM_ID, new_commit_id, SPECKLE_TOKEN)
            # st.write("Updated Dimensions:")
            # st.write("Area:", fetched_area)
            # st.write("Thickness:", fetched_thickness)



            # # # Display combined data
            # parsed_data = parse_and_display_data(client, STREAM_ID, new_commit_id, speckle_token)

    except Exception as e:
        st.error(f"Error processing data: {e}")

if __name__ == "__main__":
    main()
















