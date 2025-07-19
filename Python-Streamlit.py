from fastapi import FastAPI, Request, HTTPException, Header
from dotenv import load_dotenv
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
rhino_compute_url = "https://test.structuredd.org/io"
compute_rhino3d.Util.url = rhino_compute_url
GH_FILE_PATH = r"https://raw.githubusercontent.com/stefanovav/main/GHScript_Karamba3d_2d_Structures_Shell_22Video.gh"


def get_gh_definition(gh_file_url):
    response = requests.get(gh_file_url)
    if response.status_code == 200:
        gh_definition = response.content
        gh_definition_base64 = base64.b64encode(gh_definition).decode('utf-8')
        return gh_definition_base64
    else:
        st.error(f"Failed to fetch GH file. Status code: {response.status_code}")
        return None



# Authenticate logic with TOKEN:
def authenticate_with_speckle():
    client = SpeckleClient(host=HOST)
    speckle_token = st.secrets["TOKEN"]["value"]

    try:
        client.authenticate_with_token(speckle_token)
        if client.account and client.account.userInfo:
            st.success(f"✅ Authenticated with Speckle as: {client.account.userInfo.name}")
            return client, client.account
        else:
            st.error("❌ Authentication failed: no user info returned.")
            return None, None
    except Exception as e:
        st.error(f"❌ Authentication error: {e}")
        return None, None


# Authenticate logic with default account:
# def authenticate_with_speckle():

#     client = SpeckleClient(host=HOST)

#     # Get the default Speckle account (fetches stored login)
#     account = get_default_account()
#     if not account:
#         st.error("No Speckle account found! Please log in to your Speckle account.")
#         return None, None

#     # Authenticate the client with the fetched account
#     client.authenticate_with_account(account)
#     #speckle_token = account.token  # Dynamically fetch the token

#     st.success(f"✅ Authenticated with Speckle as: {account.userInfo.name}")
#     return client, account






def run_grasshopper(area, thickness, project_url, speckle_token, selected_model_id):
    headers = {"Content-Type": "application/json"}
    #user_area = 120  # Example area value
    #user_thickness = 60
    # Local Grasshopper file (must be open in Rhino)

    project_id = extract_project_id(project_url)

    if not project_id:
        st.error("⚠️ Invalid Speckle Project URL. Could not extract project ID.")
        return None

    full_project_url = f"https://app.speckle.systems/projects/{project_id}/models/{selected_model_id}"

#When GH file is local:
    gh_definition_base64 = get_gh_definition(GH_FILE_PATH)
    if gh_definition_base64 is None:
        return None  # stop if loading failed


# #When GH file is on GitHub:
#         response = requests.get(GH_FILE_PATH)
#         if response.status_code != 200:
#             st.error(f"❌ Failed to fetch GH file from GitHub. Status code: {response.status_code}")
#             return None
#
#         gh_definition = response.content
#         gh_definition_base64 = base64.b64encode(gh_definition).decode('utf-8')



        st.write("✅ **Verification of data:**")
        st.write("⚪ Sending Area:", area)
        st.write("⚪ Sending Thickness:", thickness)
        st.write("⚪ Project URL:", project_url)
        st.write("⚪ Speckle Token:", speckle_token[:10] + "********")

        request_data = {
            "algo": gh_definition_base64,
            "pointer": None,
            "values": [
                {"ParamName": "area", "InnerTree": {"{0}": [{"data": area}]}},
                {"ParamName": "thickness", "InnerTree": {"{0}": [{"data": thickness}]}},
                {"ParamName": "project_url", "InnerTree": {"{0}": [{"data": full_project_url}]}},
                {"ParamName": "speckle_token", "InnerTree": {"{0}": [{"data": speckle_token}]}},

            ]
        }
    print(f"Sending area: {area}, thickness: {thickness}")

    #Send request to Rhino Compute


    response = requests.post("https://test.structuredd.org/grasshopper", headers=headers, json=request_data)
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
    # client = SpeckleClient(host=HOST)
    # account = get_account_from_token(speckle_token, HOST)
    # client.authenticate_with_account(account)
    if not client:  # Ensure client is valid
        st.error("Client is not authenticated!")
        return []

    project_data = client.project.get_with_models(project_id)
    models = project_data.models.items
    #models = {model: model for model in project_data}
    return models



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


def fetch_latest_version(selected_model):
    """Extract and return version ID from the model's previewUrl."""
    # st.write("Model object:", selected_model)
    # st.write("previewUrl exists?", hasattr(selected_model, "previewUrl"))
    # st.write("previewUrl value:", getattr(selected_model, "previewUrl", None))

    preview_url = getattr(selected_model, "preview_url", None)

    if preview_url is None:
        st.error("No previewUrl found in the selected model.")
        return None

    match = re.search(r'commits/([a-f0-9]+)', preview_url)

    if match:
        return match.group(1)  # This is the version ID
    else:
        st.error("Could not extract version ID from preview URL.")
        return None





def fetch_data_from_speckle(client, project_id, version_id):
    """Fetch data from the Speckle server using the selected model only."""
    try:
        project = client.project.get(project_id)
        version = client.version.get(version_id, project_id)  # No need to fetch by version ID

        return project, version
    except Exception as e:
        st.error(f"Failed to fetch project or model: {e}")
        return None, None





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



def main():
    st.title("Utilization Values")



    # # 🟢 Step 1: Authenticate with Speckle
    client, account = authenticate_with_speckle()
    if not client or not account:  # Check if authentication failed
        return
    speckle_token = account.token



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
    selected_model = next(model for model in models if model.name == selected_model_name)
    st.write(f"Selected Model: {selected_model_name} (Model ID: {selected_model_id})")

    # 🟢 Step 4: Initialize session state for version tracking



    # latest_version= fetch_latest_version(selected_model)
    # if not latest_version:
    #     st.error("Could not fetch latest version for the selected model.")
    #     return

    latest_version_id = fetch_latest_version(selected_model)
    if not latest_version_id:
        st.error("Could not fetch latest version for the selected model.")
        return

    st.write(f"Version ID: {latest_version_id}")

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
                # latest_version = fetch_latest_version(selected_model)
                # if not latest_version:
                #     st.error("Could not fetch latest version after update.")
                #     return
                latest_version_id = fetch_latest_version(selected_model)
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
                        #
                        # st.session_state["model_loaded"] = True
                        # st.session_state["project_id"] = project_id
                        # st.session_state["selected_model_id"] = selected_model_id
                        # st.session_state["speckle_token"] = speckle_token

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
















