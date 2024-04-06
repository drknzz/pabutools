import os
import shutil

def copy_files_with_approval(directory, destination):
    if not os.path.exists(destination):
        os.makedirs(destination)

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            with open(filepath, 'rb') as file:  # Open file in binary mode
                content = file.read()
                if b"vote_type;approval" in content:  # Use bytes for comparison
                    shutil.copy(filepath, destination)
                    print(f"Copied {filename} to {destination}")

if __name__ == "__main__":
    source_directory = "tests/PaBuLib/All"
    destination_directory = "approval_data"

    copy_files_with_approval(source_directory, destination_directory)
