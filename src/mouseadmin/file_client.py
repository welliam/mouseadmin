import json
import os


class FileClient:
    def __init__(self, base_dir="mock_data"):
        """
        Initialize the FileClient with a base directory for mock data.

        Parameters
        ----------
        base_dir : str
            The directory where mock data will be stored.
        """
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(base_dir, exist_ok=True)

    def info(self, site_name=""):
        """
        Retrieve mock site information.

        Parameters
        ----------
        site_name : str
            The name of the site.

        Returns
        -------
        dict
            Mock site info.
        """
        file_path = os.path.join(self.base_dir, f"{site_name}_info.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return {"error": "Site info not found"}

    def listitems(self, site_name=""):
        """
        List mock files for a site.

        Parameters
        ----------
        site_name : str
            The name of the site.

        Returns
        -------
        dict
            List of files and metadata.
        """
        dir_path = os.path.join(self.base_dir, site_name)
        if os.path.exists(dir_path):
            files = [
                {"path": f, "size": os.path.getsize(os.path.join(dir_path, f))}
                for f in os.listdir(dir_path)
                if os.path.isfile(os.path.join(dir_path, f))
            ]
            return {"files": files}
        return {"error": "No files found"}

    def delete(self, *filenames):
        """
        Delete mock files.

        Parameters
        ----------
        filenames : str
            The names of the files to delete.

        Returns
        -------
        dict
            Result of deletion operation.
        """
        deleted = []
        for filename in filenames:
            file_path = os.path.join(self.base_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted.append(filename)
        return {"deleted": deleted, "not_found": list(set(filenames) - set(deleted))}

    def upload(self, *filenames):
        """
        Upload mock files.

        Parameters
        ----------
        filenames : tuple (str, str)
            Pairs of (local file path, mock server file name).

        Returns
        -------
        dict
            Result of upload operation.
        """
        uploaded = []
        for local_path, server_name in filenames:
            dest_path = os.path.join(self.base_dir, server_name)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(local_path, "rb") as src:
                with open(dest_path, "wb") as dest:
                    dest.write(src.read())
            uploaded.append(server_name)
        return {"uploaded": uploaded}
