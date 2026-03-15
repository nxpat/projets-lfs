# google_api_service.py
import os
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Setup the logger for this file
logger = logging.getLogger(__name__)


def create_service(client_secret_file, token_file, api_name, api_version, scopes):
    """
    Creates a Google API service.
    Expects absolute paths for both client_secret_file and token_file_path.
    """
    creds = None

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    #
    # Check for the token using the absolute path
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Google API token...")
            creds.refresh(Request())
        else:
            # Note: This will only work locally. In production, ensure token.json
            # is already uploaded and valid!
            logger.info("No valid token found. Initiating local browser flow...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
            creds = flow.run_local_server(port=0)

        # Save the credentials using the absolute path
        with open(token_file, "w") as token:
            token.write(creds.to_json())

    try:
        # Call the Google API
        service = build(api_name, api_version, credentials=creds)
        logger.info(f"{api_name} v{api_version} service created successfully!")
        return service

    except Exception as error:
        logger.error(f"An error occurred creating {api_name} service: {error}")
        return None
