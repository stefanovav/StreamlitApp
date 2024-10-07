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


# Instantiate material mappings
#MATERIALS_MAPPING1 = SteelS355()
#MATERIALS_MAPPING2 = SteelS235()

# Speckle server configuration
HOST = "speckle.xyz"
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

def send_data_to_speckle(area, thickness, stream_id, speckle_token, res):
    client = SpeckleClient(host=HOST)
    account = get_account_from_token(speckle_token, HOST)
    client.authenticate_with_account(account)

    # Modify original data structure with dimensions for the @{0;0} branch
    members_data = getattr(res, "Members", None)
    if members_data is None:
        st.error("'Members' not found in the response object.")
        return

    st.write("'Members' data found:", members_data)
    st.write("Members Data Attributes:", dir(members_data))

    # Access @{0;0} branch
    sublist0 = members_data["@{0;0}"]
    st.write("Found '@{0;0}' branch:", sublist0)

    member_obj = None

    if isinstance(sublist0, list) and len(sublist0) > 0:
        member_element = sublist0[0]  # Drill down into the next level
        st.write("First element in '@{0;0}':", member_element)

        # Attempt to access 'Member' object

        if hasattr(member_element, "@Member"):
            member_obj = getattr(member_element, "@Member", None)
        elif hasattr(member_element, "Member"):
            member_obj = getattr(member_element, "Member", None)
        elif isinstance(member_element, dict) and "Member" in member_element:
            member_obj = member_element["Member"]

        if member_obj:
            st.write("Member object found:", member_obj)

            # Check if member_obj is an instance of Mesh
            if isinstance(member_obj, Base) and member_obj.speckle_type == "Objects.Geometry.Mesh":
                st.write("Member object is a Mesh.")

                # Update attributes (if they exist or can be added)
                if hasattr(member_obj, 'area'):
                    setattr(member_obj, 'area', area)
                else:
                    st.write("'area' attribute does not exist in Mesh, adding it.")
                    member_obj.area = area  # Dynamically add if needed

                if hasattr(member_obj, 'thickness'):
                    setattr(member_obj, 'thickness', thickness)
                else:
                    st.write("'thickness' attribute does not exist in Mesh, adding it.")
                    member_obj.thickness = thickness  # Dynamically add if needed

                st.write("Updated Mesh properties:", member_obj)
            else:
                st.error("The 'Member' object is not a Mesh or a dictionary-like structure.")

        # Re-assign the modified branch back into `members_data` to preserve the overall structure
        existing_members_data = getattr(res, "Members", {})
        existing_members_data["@{0;0}"] = sublist0  # Update the modified branch
        setattr(res, "Members", existing_members_data)


    # Send updated data back to Speckle
    #base = Base(Members=members_data)
    transport = ServerTransport(client=client, stream_id=stream_id)
    obj_id = operations.send(res, [transport])

    try:
        # Create a new commit with the updated data
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


def parse_dimensions_from_commit(client, stream_id, commit_id, speckle_token):
    """Parse dimensions from the commit object."""
    try:
        # Authenticate client if necessary
        account = get_account_from_token(speckle_token, HOST)
        client.authenticate_with_account(account)

        # Fetch the commit object using the commit ID
        commit = client.commit.get(stream_id, commit_id)
        referenced_object_id = commit.referencedObject
        transport = ServerTransport(client=client, stream_id=stream_id)
        res = operations.receive(referenced_object_id, transport)

        st.write("Commit Data Received:", res)

        # Step 1: Access the 'Members' data
        members_data = getattr(res, "Members", None)
        if members_data:
            st.write("Members Data:", members_data)

            # Step 2: Access the @{0;0} branch
            sublist0 = members_data["@{0;0}"]
            if sublist0 and isinstance(sublist0, list) and len(sublist0) > 0:
                st.write("Sublist0 Data:", sublist0)

                # Step 3: Access the first element in sublist0 (directly an object)
                member_element = sublist0[0]

                # Attempt to access '@Member' or 'Member' directly
                member_obj = None
                if hasattr(member_element, "@Member"):
                    member_obj = getattr(member_element, "@Member", None)
                elif hasattr(member_element, "Member"):
                    member_obj = getattr(member_element, "Member", None)
                elif isinstance(member_element, dict) and "Member" in member_element:
                    member_obj = member_element["Member"]

                if member_obj:
                    st.write("Member object found:", member_obj)

                    # Check if member_obj has area and thickness attributes
                    if hasattr(member_obj, 'area'):
                        fetched_area = member_obj.area
                    if hasattr(member_obj, 'thickness'):
                        fetched_thickness = member_obj.thickness
                        return fetched_area, fetched_thickness
                    else:
                        st.error("The 'Member' object does not have an 'area' or 'thickness' attribute.")
                        return 0, 0
        # Default return if dimensions not found
        return 0, 0
    except Exception as e:
        st.error(f"Error parsing dimensions from commit: {e}")
        return 0, 0


def parse_and_display_data(client, stream_id, commit_id, speckle_token):
    """Fetch and parse material data from the commit object and display it in a table."""
    try:
        # Authenticate client if necessary
        account = get_account_from_token(speckle_token, HOST)
        client.authenticate_with_account(account)

        # Fetch the commit object using the commit ID
        commit = client.commit.get(stream_id, commit_id)
        referenced_object_id = commit.referencedObject
        transport = ServerTransport(client=client, stream_id=stream_id)
        res = operations.receive(referenced_object_id, transport)

        # Getting data for the members of the commit in the list Members -> @0
        moment_data = getattr(res, "Moment Value", None)

        if moment_data:
            sublist1 = getattr(moment_data, "@{0}", None)  # Retrieve the '@{0}' attribute

            if isinstance(sublist1, list):  # Check if sublist1 is a list
                combined_data = [{'Moment Value': value} for value in sublist1]  # Create combined_data
                display_combined_table(combined_data)  # Directly display the table
            else:
                print(f"Unexpected data type: {type(sublist1)}")  # For debugging

        else:
            st.error("No moment data found.")

    except Exception as e:
        st.error(f"Error parsing material data from commit: {e}")



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


def main():
    global COMMIT_FILE_PATH
    new_commit_id = None  # Initialize new_commit_id before use

    st.title("Speckle Moment Values on a Concrete Shell")

    # Step 1: Get the latest commit ID from the file
    COMMIT_ID = get_latest_commit_id(COMMIT_FILE_PATH)
    if not COMMIT_ID:
        st.error("Failed to retrieve the latest commit ID.")
        return

    # Step 2: Enter Speckle Token
    speckle_token = os.getenv("SPECKLE_TOKEN")
    SPECKLE_TOKEN = st.text_input("Enter Speckle Token:", value=speckle_token, type = "password")

    st.write("Entered Commit ID from Grasshopper:", COMMIT_ID)
    #st.write("Entered Speckle Token:", speckle_token)

    # Step 3: User inputs for area and thickness
    area = st.number_input("Enter area, [m²]:", min_value=1.0, step=0.1)
    thickness = st.number_input("Enter thickness, [cm]:", min_value=1.0, step=0.1)

    if st.button("Send Data to Speckle"):
        if SPECKLE_TOKEN:
            stream, commit = fetch_data_from_speckle(STREAM_ID, COMMIT_ID, SPECKLE_TOKEN)
            if not stream or not commit:
                st.error("Failed to fetch stream or commit. Please check your Speckle server setup.")
                return

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
        st.write("Successfully authenticated with Speckle for sending data.")

        transport = ServerTransport(client=client, stream_id=STREAM_ID)
        res = operations.receive(commit.referencedObject, transport)

        if res:

            transformed_res = transform_keys_to_integers(copy.deepcopy(res))
            st.write("Transformed Data for Display:", transformed_res)

            members_data = getattr(res, "Members", None)
            if members_data is None:
                st.error("'Members' not found in the response object.")
                return

            sublist0 = members_data["@{0;0}"]
            st.write("Found '@{0;0}' branch:", sublist0)

            member_obj = None

            if isinstance(sublist0, list) and len(sublist0) > 0:
                member_element = sublist0[0]

                if hasattr(member_element, "Member"):
                    member_obj = getattr(member_element, "Member", None)

                if member_obj:
                    st.write("Member object found:", member_obj)

                    if isinstance(member_obj, Base) and member_obj.speckle_type == "Objects.Geometry.Mesh":
                        st.write("Member object is a Mesh.")

                        if hasattr(member_obj, 'area'):
                            setattr(member_obj, 'area', area)
                        else:
                            st.write("'area' attribute does not exist in Mesh, adding it.")
                            member_obj.area = area  # Dynamically add if needed

                        if hasattr(member_obj, 'thickness'):
                            setattr(member_obj, 'thickness', thickness)
                        else:
                            st.write("'thickness' attribute does not exist in Mesh, adding it.")
                            member_obj.thickness = thickness  # Dynamically add if needed

                        st.write("Updated Mesh properties:", member_obj)

                    else:
                        st.error("The 'Member' object is not a Mesh or a dictionary-like structure.")

    # Step 4: Re-assign the modified branch back into `members_data` to preserve the overall structure
            existing_members_data = getattr(res, "Members", {})
            existing_members_data["@{0;0}"] = sublist0  # Update the modified branch
            setattr(res, "Members", existing_members_data)

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

            fetched_area, fetched_thickness = parse_dimensions_from_commit(client, STREAM_ID, new_commit_id, SPECKLE_TOKEN)
            st.write("Updated Dimensions:")
            st.write("Area:", fetched_area)
            st.write("Thickness:", fetched_thickness)

            # # Display combined data
            parsed_data = parse_and_display_data(client, STREAM_ID, new_commit_id, speckle_token)

    except Exception as e:
        st.error(f"Error processing data: {e}")

if __name__ == "__main__":
    main()
















