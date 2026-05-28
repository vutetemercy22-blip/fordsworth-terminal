import streamlit as st

from services.google_drive_service import (
    credentials_file_exists,
    create_drive_folder,
    upload_file_to_drive,
    list_recent_drive_files,
)
from services.report_service import export_research_pack_to_docx

st.set_page_config(page_title="Google Drive Sync", page_icon="☁️", layout="wide")

st.title("Google Drive Sync")
st.caption("Upload generated research packs to Google Drive.")

st.divider()

if not credentials_file_exists():
    st.error(
        "Google Drive credentials file is missing. "
        "Create credentials/google_service_account.json first."
    )

    st.markdown(
        """
        ### Required setup

        1. Create a Google Cloud project  
        2. Enable the Google Drive API  
        3. Create a service account  
        4. Download the service-account JSON key  
        5. Rename it to:

        ```text
        google_service_account.json
        ```

        6. Save it here:

        ```text
        credentials/google_service_account.json
        ```

        7. Share your target Google Drive folder with the service-account email.
        """
    )

else:
    st.success("Google Drive credentials file found.")

    st.subheader("Upload Latest Research Pack")

    include_deep_digger = st.checkbox(
        "Include latest Deep Digger memo",
        value=True,
    )

    folder_id = st.text_input(
        "Google Drive folder ID",
        placeholder="Paste folder ID here, or leave blank to upload to service account root",
    )

    if st.button("Export and Upload Research Pack"):
        with st.spinner("Exporting latest research pack..."):
            research_pack_path = export_research_pack_to_docx(
                include_deep_digger=include_deep_digger,
            )

        with st.spinner("Uploading to Google Drive..."):
            uploaded_file = upload_file_to_drive(
                local_file_path=research_pack_path,
                folder_id=folder_id.strip() or None,
            )

        st.success("Research Pack uploaded to Google Drive.")

        st.markdown(
            f"""
            **File:** {uploaded_file.get("name")}  
            **Google Drive ID:** `{uploaded_file.get("id")}`  
            **Open:** {uploaded_file.get("webViewLink", "No link returned")}
            """
        )

    st.divider()

    st.subheader("Create Google Drive Folder")

    new_folder_name = st.text_input(
        "New folder name",
        value="Portfolio Intelligence Terminal Reports",
    )

    if st.button("Create Folder in Google Drive"):
        folder_id_created = create_drive_folder(new_folder_name)
        st.success("Folder created.")
        st.code(folder_id_created)
        st.info(
            "Copy this folder ID and use it in the upload section above."
        )

    st.divider()

    st.subheader("Recent Drive Files")

    if st.button("Refresh Recent Drive Files"):
        files = list_recent_drive_files(limit=10)

        if not files:
            st.info("No recent files found.")
        else:
            for file in files:
                st.markdown(
                    f"""
                    **{file.get("name")}**  
                    Type: `{file.get("mimeType")}`  
                    Modified: {file.get("modifiedTime")}  
                    Link: {file.get("webViewLink", "No link")}
                    """
                )
                st.divider()