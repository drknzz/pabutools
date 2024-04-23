import sys
import json
import os

def remove_key(dictionary, key_to_remove):
    if not isinstance(dictionary, dict):
        return dictionary
    for key, value in list(dictionary.items()):
        if key == key_to_remove:
            del dictionary[key]
        else:
            dictionary[key] = remove_key(value, key_to_remove)
    return dictionary

if __name__ == "__main__":
    file_name = sys.argv[1]
    
    # Split the file_name into directory part and file name
    directory, filename_with_extension = os.path.split(file_name)
    
    # Split the filename and extension
    filename, extension = os.path.splitext(filename_with_extension)

    with open(file_name) as f:
        content = f.read()

    res = json.loads(content)

    res = remove_key(res, "payment_functions")

    # Construct the new file name with _slim suffix
    new_filename = f"{filename}_slim{extension}"

    # Construct the full path for the new file
    new_file_path = os.path.join(directory, new_filename)

    with open(new_file_path, "w") as f:
        s = json.dumps(
            res,
            sort_keys=True,
            indent=4
        )
        f.write(s)