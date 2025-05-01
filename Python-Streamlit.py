import streamlit as st
import plotly.graph_objects as go
import requests
from specklepy.api import operations
from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import get_default_account
#from specklepy.api.client import ModelResource
from specklepy.transports.server import ServerTransport
from specklepy.api.credentials import get_account_from_token
from specklepy.objects import Base
from datetime import datetime
from operator import itemgetter
import re
import os
import copy
import streamlit.components.v1 as components
import specklepy
from specklepy.api.wrapper import StreamWrapper
import compute_rhino3d.Util as rhutil
import compute_rhino3d.Curve
# import compute_rhino3d.Grasshopper as gh
# from compute_rhino3d.Grasshopper import DataTree
# import compute_rhino3d as compute
import json
# from compute_rhino3d.Util import url as rhino_url
# from compute_rhino3d.Grasshopper import EvaluateDefinition
from specklepy.transports.memory import MemoryTransport
from specklepy.api.resources.current.version_resource import CreateVersionInput
from specklepy.core.api.models import (
    Model,
    ModelWithVersions,
    Project,
    ResourceCollection,
    Version,
)
from flask import Flask, request, jsonify
import asyncio
import httpx
from concurrent.futures import ThreadPoolExecutor
import base64
import plotly.graph_objects as go
import time

# Speckle server configuration
HOST = "https://app.speckle.systems"
rhino_compute_url = "http://localhost:6500/io"
compute_rhino3d.Util.url = rhino_compute_url
GH_FILE_PATH = "https://raw.githubusercontent.com/stefanovav/StreamliApp/main/22.Video/250218_GHScript_Karamba3d_STB%20Platte-1.gh"
WEBHOOK_URL = "https://speckle-webhook-nx44ryeaaq-nw.a.run.app/latest"




# client = None
# account = None
# speckle_token = None

# async def test_simple_request():
#     try:
#         # Define the Grasshopper definition URL or local path
#         with open(GH_FILE_PATH, "rb") as file:
#             gh_definition = file.read()
#             gh_definition_base64 = base64.b64encode(gh_definition).decode('utf-8')
#         # Sending the request with the definition and some dummy values
#         request_data = {
#             "algo": gh_definition_base64,  # The Grasshopper definition URL or path
#             "values": [
#                 {"area": 100},  # Example input, if your GH file expects "area"
#                 {"thickness": 10}  # Example input, if your GH file expects "thickness"
#             ]
#         }
#
#         async with httpx.AsyncClient(timeout=300) as client:
#             response = await client.post("http://localhost:6500/io", json=request_data)
#             if response.status_code == 200:
#                 data = response.json()
#
#             print(f"✅ Full Response: {data}")
#
#
#     except httpx.RequestError as e:
#         print(f"⚠️ Error: Could not connect to Rhino Compute. {str(e)}")
#
# # Run the request
# asyncio.run(test_simple_request())


def authenticate_with_speckle():

    client = SpeckleClient(host=HOST)
    speckle_token = st.secrets["TOKEN"]
    client.authenticate_with_token(speckle_token)


    # Authenticate the client with the fetched account
    #client.authenticate_with_account(account)
    #speckle_token = account.token  # Dynamically fetch the token

    st.success(f"✅ Authenticated with Speckle as: {client.user.name}")
    return client, client.account

# @st.cache_data(ttl=10)
# def check_latest_version():
#     """Check if a new version is available from the webhook."""
#     try:
#         response = requests.get(WEBHOOK_URL)
#         if response.status_code == 200:
#             data = response.json()
#             if "versionId" in data:
#                 if data["versionId"] != st.session_state.get("latest_version_id"):
#                     st.session_state["is_webhook_update"] = True  # ✅ Webhook triggered update
#                 return data["versionId"]
#     except Exception as e:
#         st.error(f"Error checking webhook: {e}")
#     return None


#
# def check_and_update_version():
#     """Check for a new version from webhook and update Streamlit if needed."""
#     newest_version = check_latest_version()
#
#     if newest_version and newest_version != st.session_state["latest_version_id"]:
#         if st.session_state["is_user_update"]:
#             st.session_state["is_user_update"] = False  # ✅ Reset flag
#         else:
#             st.session_state["latest_version_id"] = newest_version
#             st.experimental_rerun()  # 🔄 Refresh Streamlit to load new data




def run_grasshopper(area, thickness, project_url, speckle_token, selected_model_id):
    headers = {
        "Content-Type": "application/json"
    }
    #user_area = 120  # Example area value
    #user_thickness = 60
    # Local Grasshopper file (must be open in Rhino)

    project_id = extract_project_id(project_url)

    if not project_id:
        st.error("⚠️ Invalid Speckle Project URL. Could not extract project ID.")
        return None

    full_project_url = f"https://app.speckle.systems/projects/{project_id}/models/{selected_model_id}"

    with open(GH_FILE_PATH, "rb") as file:
        gh_definition = file.read()
        gh_definition_base64 = base64.b64encode(gh_definition).decode('utf-8')

        st.write("✅ **Verification of data:**")
        st.write("⚪ Sending Area:", area)
        st.write("⚪ Sending Thickness:", thickness)
        st.write("⚪ Project URL:", project_url)
        st.write("⚪ Speckle Token:", speckle_token[:10] + "********")

        request_data = {
            "algo": gh_definition_base64,
            "pointer": None,
            "values": [
                {"ParamName": "project_url", "InnerTree": {"{0}": [{"data": full_project_url}]}},
                {"ParamName": "speckle_token", "InnerTree": {"{0}": [{"data": speckle_token}]}},
                {"ParamName": "area", "InnerTree": {"{0}": [{"data": area}]}},
                {"ParamName": "thickness", "InnerTree": {"{0}": [{"data": thickness}]}}
            ]
        }
    print(f"Sending area: {area}, thickness: {thickness}")

    # Send request to Rhino Compute
    response = requests.post("http://localhost:6500/grasshopper", headers=headers, json=request_data)
    print("Response Status Code:", response.status_code)
    print("Response Text:", response.text)
    if response.status_code == 200:
        return response.json()  # ✅ Return the response data
    else:
        return None




def extract_project_id(url):
    match = re.search(r'/projects/([a-zA-Z0-9]+)', url)
    return match.group(1) if match else None

def fetch_models(client, project_id):
    #client = SpeckleClient(host=HOST)
    # account = get_account_from_token(speckle_token, HOST)
    # client.authenticate_with_account(account)
    if not client:  # Ensure client is valid
        st.error("Client is not authenticated!")
        return []

    project_data = client.project.get_with_models(project_id)
    models = project_data.models.items
    #models = {model: model for model in project_data}
    return models



# def find_and_update_mesh(members_data, area, thickness):
#     # Initialize as a dictionary to preserve branch keys
#     updated_members_data = {}
#
#     branch_keys = [key for key in dir(members_data) if key.startswith("@{")]
#
#     for branch_key in branch_keys:
#         branch_value = getattr(members_data, branch_key, None)
#
#         if isinstance(branch_value, list):
#             updated_branch = []
#             for element in branch_value:
#                 member_obj = getattr(element, "Member", None)
#                 if member_obj and member_obj.speckle_type == "Objects.Geometry.Mesh":
#                     member_obj.area = area
#                     member_obj.thickness = thickness
#                 updated_branch.append(element)
#
#             # Store the updated branch under its key
#             updated_members_data[branch_key] = updated_branch
#
#     return updated_members_data


def find_utilization_value(members_data):
    """Extract utilization values from members data and return as a structured dictionary."""
    utilization_data = []

    # Find all branch keys (e.g., "@{0;0}", "@{0;1}", etc.)
    branch_keys = [key for key in dir(members_data) if key.startswith("@{")]

    for branch_key in branch_keys:
        branch_value = getattr(members_data, branch_key, None)

        if isinstance(branch_value, list):
            for element in branch_value:
                utilization_value = getattr(element, "Utilization", None)
                if utilization_value is not None:
                    utilization_data.append({"Branch": branch_key, "Utilization": utilization_value})

    return utilization_data




def fetch_latest_version(client, project_id, model_id):
    """Fetch the latest version ID of a model within a given project."""
    #client = SpeckleClient(host=HOST)
    # account = get_account_from_token(speckle_token, HOST)
    # client.authenticate_with_account(account)

    try:
        # Fetch the model with versions
        model_with_versions = client.version(model_id=model_id, project_id=project_id)

        # Debug: Check if there are versions
        if not model_with_versions.versions or not model_with_versions.versions.items:
            st.error(f"Model {model_id} has no versions.")
            return None

        # Debug: Print available versions

        for version in model_with_versions.versions.items:
            latest_version = max(
                model_with_versions.versions.items,
                key=lambda v: datetime.fromisoformat(str(version.createdAt))  # Convert createdAt to datetime
            )

        # Print latest version details
        st.write(f"Latest Version ID: {latest_version.id}, , Created At: {latest_version.createdAt}")

        return latest_version.id  # Return the latest version ID

    except Exception as e:
        st.error(f"Error fetching latest version: {e}")
        return None





#@st.cache_data(ttl=300)
def fetch_data_from_speckle(client, project_id, version_id):
    """Fetch data from the Speckle server."""
    # client = SpeckleClient(host=HOST)
    # account = get_account_from_token(speckle_token, HOST)
    # client.authenticate_with_account(account)

    try:
        #st.write(f"Latest Version ID: {version_id}")
        project = client.project.get(project_id)
        version = client.version.get(version_id, project_id)
        return project, version
    except Exception as e:
        st.error(f"Failed to fetch project or version: {e}")
        return None, None



# def send_data_to_speckle(client, area, thickness, project_id, model_id, speckle_token, res):
#     st.write(f"Confirmed Model ID: {model_id}")
#     # client = SpeckleClient(host=HOST)
#     # account = get_account_from_token(speckle_token, HOST)
#     # client.authenticate_with_account(account)
#     account = client.account
#     #Access Members data
#     members_data = getattr(res, "@data", None)
#     if members_data is None:
#         st.error("'@data' not found in the response object.")
#         return
#
#     # Use find_and_update_mesh to update the data
#     updated_members_data = find_and_update_mesh(members_data, area, thickness)
#
#     # Reassign the updated structure back to `res.Members`
#     for branch_key, updated_branch in updated_members_data.items():
#         setattr(members_data, branch_key, updated_branch)
#     setattr(res, "@data", members_data)
#
#
#     # Send updated data back to Speckle
#     transport = ServerTransport(client=client, stream_id=project_id, account=account)
#     obj_id = operations.send(res, [transport])
#
#
#     input_data = CreateVersionInput(
#         objectId=obj_id,
#         modelId=model_id,
#         projectId=project_id
#     )
#
#     new_version_id = client.version.create(input_data)  # Create and get version ID
#
#     return new_version_id



def versionviewer(project_id, model_id, speckle_token):
    """Embed Speckle viewer."""
    height = 600  # Default height for the viewer
    if project_id and model_id:
        embed_src = f"https://app.speckle.systems/projects/{project_id}/models/{model_id}?access_token={speckle_token}"
        st.write(f"Embed URL: {embed_src}")  # Debugging line to confirm embed URL
        components.iframe(embed_src, height=height, scrolling=True)
    else:
        st.error("Unable to display viewer: version ID is not available.")


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


# def display_combined_table(combined_data):
#     """Display the combined data in a Plotly table."""
#
#     # Calculate the height dynamically based on the number of rows
#     num_rows = len(combined_data)
#     row_height = 30  # Adjust this value as needed
#     table_height = num_rows * row_height
#
#     header_values = list(combined_data[0].keys())
#     cell_values = [list(col) for col in zip(*[list(row.values()) for row in combined_data])]
#
#     fig = go.Figure(data=[go.Table(
#         header=dict(
#             values=header_values,
#             fill_color='paleturquoise',
#             align='left',
#             font=dict(size=16)  # Set header font size to 16
#         ),
#         cells=dict(
#             values=cell_values,
#             fill_color='#F5F5F5',
#             align='left',
#             font=dict(size=14)  # Set cell font size to 14
#         )
#     )])
#
#     # Update the layout to adjust the height
#     fig.update_layout(
#         height=table_height,
#         margin=dict(t=0, b=0, pad=0)
#     )
#
#     st.plotly_chart(fig)


def main():
    st.title("Utilization Values")
    # st.image(
    #     "https://raw.githubusercontent.com/stefanovav/StreamlitApp/main/Model.png",
    #     caption="App Thumbnail",
    #     width=400  # Set width in pixels
    # )

    if (
            "model_loaded" in st.session_state and st.session_state["model_loaded"]
            and "project_id" in st.session_state
            and "selected_model_id" in st.session_state
            and "speckle_token" in st.session_state
    ):
        versionviewer(
            st.session_state["project_id"],
            st.session_state["selected_model_id"],
            st.session_state["speckle_token"]
        )
    else:
        st.image(
            "https://raw.githubusercontent.com/stefanovav/StreamlitApp/main/Model.png",
            caption="App Thumbnail",
            width=400
        )



    # # 🟢 Step 1: Authenticate with Speckle
    client, account = authenticate_with_speckle()
    if not client or not account:  # Check if authentication failed
        return
    


    # 🟢 Step 2: Get Project URL and Extract ID
    project_url = st.text_input("Enter Speckle Project URL:")
    if not project_url:
        return

    project_id = extract_project_id(project_url)
    if not project_id:
        st.error("Invalid Project URL.")
        return

    st.write(f"Extracted Project ID: {project_id}")

    # 🟢 Step 3: Fetch Available Models
    models = fetch_models(client, project_id)
    if not models:
        st.error("No models found in this project.")
        return

    model_dict = {model.name: model.id for model in models}
    selected_model_name = st.selectbox("Select a model:", list(model_dict.keys()))
    selected_model_id = model_dict[selected_model_name]
    #selected_model = next(model for model in models if model.name == selected_model_name)
    st.write(f"Selected Model: {selected_model_name} (Model ID: {selected_model_id})")

    # 🟢 Step 4: Initialize session state for version tracking

    latest_version_id = fetch_latest_version(client, project_id, selected_model_id)
    if not latest_version_id:
        st.error("Could not fetch latest version for the selected model.")
        return

    project, version = fetch_data_from_speckle(client, project_id, latest_version_id)
    if not project or not version:
        st.error("Failed to fetch stream or commit. Please check your Speckle server setup.")
        return


    # 🟢 Step 5: User Inputs for Area and Thickness
    area = st.number_input("Enter area, [m²]:", min_value=1.0, step=0.1)
    thickness = st.number_input("Enter thickness, [cm]:", min_value=1.0, step=0.1)

    # 🟢 Step 6: Run Grasshopper and Send Data to Speckle
    if st.button("Send Data to Speckle"):
        if not project_url or not speckle_token:
            st.error("Project URL and Speckle Token are required.")
            return

        st.write("🚀 Running Grasshopper Script...")
        response = run_grasshopper(area, thickness, project_url, speckle_token, selected_model_id)

        if response:
            st.success("✅ Successfully ran Grasshopper script!")
            #st.json(response)
            #st.write(f"Extracted Speckle Project ID: {project_id}")

            try:
                # 🟢 Step 7: Fetch the Newest Version from Speckle
                latest_version_id = fetch_latest_version(client, project_id, selected_model_id)
                if not latest_version_id:
                    st.error("Could not fetch latest version after update.")
                    return

                project, version = fetch_data_from_speckle(client, project_id, latest_version_id)
                if not project or not version:
                    st.error("Failed to fetch the updated model from Speckle.")
                    return

                # 🟢 Step 8: Extract and Display Utilization Value
                transport = ServerTransport(client=client, stream_id=project_id, account=account)
                res = operations.receive(version.referencedObject, transport)

                if res:
                    members_data = getattr(res, "@data", None)
                    utilization_values = find_utilization_value(members_data)
                    if utilization_values:
                        # Extract the first utilization value and round it
                        rounded_utilization = round(utilization_values[0]["Utilization"], 2)
                        #st.session_state["last_utilization"] = rounded_utilization

                        st.session_state["model_loaded"] = True
                        st.session_state["project_id"] = project_id
                        st.session_state["selected_model_id"] = selected_model_id
                        st.session_state["speckle_token"] = speckle_token

                        # Determine status and color based on utilization value
                        status = "OK" if rounded_utilization <= 1 else "!"
                        color = "lightgreen" if rounded_utilization <= 1 else "lightcoral"

                        # Create the table with conditional formatting
                        fig = go.Figure(data=[go.Table(
                            header=dict(values=["Utilization Value", "Threshold (1.00)", "Status"],
                                        fill_color="paleturquoise",
                                        align="center",
                                        font=dict(size=16),
                                        height=40,
                                        line=dict(color="black", width=2)
                            ),
                            cells=dict(
                                values=[
                                    [rounded_utilization],  # Utilization Value
                                    [1.00],  # Threshold
                                    [status]  # Status (OK / !)
                                ],
                                fill_color=[["white"], ["white"], [color]],
                                align="center",
                                font=dict(size=14, family="Arial"),
                                height=40,
                                line=dict(color="black", width=2)
                            )
                        )])

                        # Display in Streamlit
                        #st.write(f"✅ Utilization Value: {rounded_utilization}")
                        st.plotly_chart(fig)

                    # 🟢 Step 9: Update Speckle with the New Version
                    # new_version_id = send_data_to_speckle(client, area, thickness, project_id, selected_model_id,
                    #                                       speckle_token, res)
                    # if new_version_id:
                    #     st.write("✅ New Version ID:", new_version_id)
                    #     st.write("🔄 Data Sent: Area =", area, "Thickness =", thickness)

                        # 🟢 Step 10: Update the Viewer with the Latest Model
                        versionviewer(project_id, selected_model_id, speckle_token)
                    else:
                        st.error("⚠️ Failed to update and send data to Speckle.")
                else:
                    st.error("⚠️ Failed to receive updated geometry data from Speckle.")

            except Exception as e:
                st.error(f"⚠️ Error sending data to Speckle: {e}")
                return

if __name__ == "__main__":
    main()
















