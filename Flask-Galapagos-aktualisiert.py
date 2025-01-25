import streamlit as st
import plotly.graph_objects as go
import requests
from flask import Flask
from specklepy.api import operations
from specklepy.api.client import SpeckleClient
from specklepy.api.client import ModelResource
from specklepy.transports.server import ServerTransport
from specklepy.api.credentials import get_account_from_token
from specklepy.objects import Base
import os
import copy
import streamlit.components.v1 as components
import specklepy
from specklepy.api.wrapper import StreamWrapper
# import compute_rhino3d.Util
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





# compute_rhino3d.Util.url = r'http://localhost:6500/'.encode('utf-8')




# Speckle server configuration
HOST = "https://app.speckle.systems"
PROJECT_ID = "791d494b2e"
#OBJECT_ID = "166492fae4d3e8fc9c3d6e70edd0981a"
stream_id = PROJECT_ID
BRANCH_NAME = "shell"


VERSION_FILE_PATH = r"CommitID.txt"  # Update with your file path

def get_latest_version_id(file_path):
    """Retrieve the latest commit ID from a file."""
    try:
        with open(file_path, 'r') as f:
            version_id = f.read().strip()
        return version_id
    except FileNotFoundError:
        st.error("Commit ID file not found.")
        return None


def find_and_update_mesh(members_data, area, thickness):
    # Initialize as a dictionary to preserve branch keys
    updated_members_data = {}

    branch_keys = [key for key in dir(members_data) if key.startswith("@{")]

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

            # Store the updated branch under its key
            updated_members_data[branch_key] = updated_branch

    return updated_members_data




def send_data_to_speckle(area, thickness, project_id, speckle_token, res):
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
    transport = ServerTransport(client=client, stream_id=stream_id, account=account)
    obj_id = operations.send(res, [transport])



    st.write(f"Generated object ID: {obj_id}")

    project_data = client.project.get_with_models(PROJECT_ID)
    model = project_data.models.items[0]
    #model = next(m for m in project_data.models.items if m.name == BRANCH_NAME)



    st.write(f"Model_id: {(model.id)}")


    input_data = CreateVersionInput(
        objectId=obj_id,
        modelId=model.id,
        projectId=project_data.id
    )
    st.write(f"Input data being sent: {input_data}")
    new_version_id = client.version.create(input_data)  # Create and get version ID
    st.write(f"Type of new_version_id: {type(new_version_id)}")
    return new_version_id


@st.cache_data(ttl=300)
def fetch_data_from_speckle(project_id, version_id, speckle_token):
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
        st.write(f"GraphQL Query Variables: {{ 'versionId': {version_id} }}")
        project = client.project.get(project_id)
        version = client.version.get(version_id, project_id)
        return project, version
    except Exception as e:
        st.error(f"Failed to fetch project or version: {e}")
        return None, None


def commit2viewer(project_id, model_id, speckle_token):
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
    global VERSION_FILE_PATH
    new_version_id = None  # Initialize new_version_id

    st.title("Speckle Moment Values on a Concrete Shell")

    # Step 1: Get the latest commit ID from the file
    VERSION_ID = get_latest_version_id(VERSION_FILE_PATH)
    if not VERSION_ID:
        st.error("Failed to retrieve the latest version ID.")
        return

    SPECKLE_TOKEN_APP = os.getenv("SPECKLE_TOKEN_APP")
    if SPECKLE_TOKEN_APP:
        st.success("Speckle Token successfully retrieved from the environment.")
    else:
        SPECKLE_TOKEN_APP = st.text_input("Enter Speckle Token:", type="password")
        if not SPECKLE_TOKEN_APP:
            st.error("Speckle Token is required to proceed.")
            st.stop()

    # # Initialize variables
    # client = None  # Declare `client` to avoid "referenced before assignment" error
    # project = None
    # version_id = None
    # model_id = None

    try:
        # Authenticate with Speckle
        client = SpeckleClient(host=HOST)
        account = get_account_from_token(SPECKLE_TOKEN_APP, HOST)
        client.authenticate_with_account(account)
        st.success("Successfully authenticated with Speckle.")

        # Retrieve project and model data
        project_data = client.project.get_with_models(PROJECT_ID)
        model = next((m for m in project_data.models.items if m.name == "shell"), None)
        if not model:
            st.error("Model 'shell' not found in the project.")
            return

        model_id = model.id
        st.write(f"Model ID retrieved: {model_id}")

        # Fetch data from Speckle server
        project, version = fetch_data_from_speckle(PROJECT_ID, VERSION_ID, SPECKLE_TOKEN_APP)
        if not project or not version:
            st.error("Failed to fetch stream or commit. Please check your Speckle server setup.")
            return

    except Exception as e:
        st.error(f"Failed to initialize Speckle client or retrieve project data: {e}")
        return

    # Step 3: User inputs for area and thickness
    area = st.number_input("Enter area, [m²]:", min_value=1.0, step=0.1)
    thickness = st.number_input("Enter thickness, [cm]:", min_value=1.0, step=0.1)

    if st.button("Send Data to Speckle"):
        try:
            transport = ServerTransport(client=client, stream_id=stream_id, account=account)
            res = operations.receive(version.referencedObject, transport)

            if res:
                new_version_id = send_data_to_speckle(area, thickness, PROJECT_ID, SPECKLE_TOKEN_APP, res)
                if new_version_id:
                    st.write("New version ID:", new_version_id)
                    st.write("Sent data: Area =", area, "Thickness =", thickness)

                    # Embed viewer with correct model ID
                    commit2viewer(PROJECT_ID, model_id, SPECKLE_TOKEN_APP)
                else:
                    st.error("Failed to update and send data to Speckle.")
            else:
                st.error("Failed to receive geometry data from Speckle.")
        except Exception as e:
            st.error(f"Error sending data to Speckle: {e}")
            return

    # # Embed viewer for the project and model
    # try:
    #     if model_id:
    #         commit2viewer(PROJECT_ID, model_id, SPECKLE_TOKEN_APP)
    # except Exception as e:
    #     st.error(f"Error embedding viewer: {e}")


if __name__ == "__main__":
    main()
















