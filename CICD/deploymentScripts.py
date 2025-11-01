import zipfile
import tempfile 
import shutil
import os

#bash scripts for fastapi
stop_sh_template = """#!/bin/bash
pkill -f "uvicorn|gunicorn|fastapi" || true

"""

install_sh_template = """
#!/bin/bash
set -e
cd /home/ubuntu/app

sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip

python3 -m venv .venv
. .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install uvicorn


"""

start_sh_template = """#!/bin/bash
set -euo pipefail
cd /home/ubuntu/app
source .venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /var/log/fastapi.out 2>&1 &


"""



def addStartScript(zip_path,buildSpec,overWrite=True): #build spec template
    

    with zipfile.ZipFile(zip_path, 'r') as zin:  #open zip file and read it 
        names = zin.namelist() #returns a list of file paths 

        if not names: 
           
            raise ValueError("Zip file is empty.")
            return
        
        rootFolder = names[0]

        root_prefix = rootFolder.split("/")[0] + "/"

        target_path = root_prefix + "scripts/start.sh"
        print("Target path for appspec:", target_path)

        has_buildspec = target_path in names

   
        tmp_dir,tmp_zip_path = tempfile.mkstemp() #makes temporary empty file

        os.close(tmp_dir) #temp_dir is a file descriptor not needed so we close it
        try:
            with zipfile.ZipFile(tmp_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in names:
                    # Skip the old buildspec if we're overwriting
                    if overWrite and item == target_path:
                        continue
                    data = zin.read(item)
                    zout.writestr(item, data)

    
                zout.writestr(target_path, buildSpec)

            
            shutil.move(tmp_zip_path, zip_path)

            if has_buildspec and overWrite:
                print("Replaced existing start.sh in ZIP.")
          
            else:
                print("Injected start.sh into ZIP.")
               # print(names)
        finally:
           
            if os.path.exists(tmp_zip_path):
                try:
                    os.remove(tmp_zip_path)
                except OSError:
                    pass

def addStopScript(zip_path,buildSpec,overWrite=True): #build spec template
    

    with zipfile.ZipFile(zip_path, 'r') as zin:  #open zip file and read it 
        names = zin.namelist() #returns a list of file paths 

        if not names: 
           
            raise ValueError("Zip file is empty.")
            return
        
        rootFolder = names[0]

        root_prefix = rootFolder.split("/")[0] + "/"

        target_path = root_prefix + "scripts/stop.sh"
        print("Target path for appspec:", target_path)

        has_buildspec = target_path in names

   
        tmp_dir,tmp_zip_path = tempfile.mkstemp() #makes temporary empty file

        os.close(tmp_dir) #temp_dir is a file descriptor not needed so we close it
        try:
            with zipfile.ZipFile(tmp_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in names:
                    # Skip the old buildspec if we're overwriting
                    if overWrite and item == target_path:
                        continue
                    data = zin.read(item)
                    zout.writestr(item, data)

    
                zout.writestr(target_path, buildSpec)

            
            shutil.move(tmp_zip_path, zip_path)

            if has_buildspec and overWrite:
                print("Replaced existing start.sh in ZIP.")
          
            else:
                print("Injected start.sh into ZIP.")
               # print(names)
        finally:
           
            if os.path.exists(tmp_zip_path):
                try:
                    os.remove(tmp_zip_path)
                except OSError:
                    pass
    

def addInstallScript(zip_path,buildSpec,overWrite=True): #build spec template
    

    with zipfile.ZipFile(zip_path, 'r') as zin:  #open zip file and read it 
        names = zin.namelist() #returns a list of file paths 

        if not names: 
           
            raise ValueError("Zip file is empty.")
            return
        
        rootFolder = names[0]

        root_prefix = rootFolder.split("/")[0] + "/"

        target_path = root_prefix + "scripts/install.sh"
        print("Target path for appspec:", target_path)

        has_buildspec = target_path in names

   
        tmp_dir,tmp_zip_path = tempfile.mkstemp() #makes temporary empty file

        os.close(tmp_dir) #temp_dir is a file descriptor not needed so we close it
        try:
            with zipfile.ZipFile(tmp_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in names:
                    # Skip the old buildspec if we're overwriting
                    if overWrite and item == target_path:
                        continue
                    data = zin.read(item)
                    zout.writestr(item, data)

    
                zout.writestr(target_path, buildSpec)

            
            shutil.move(tmp_zip_path, zip_path)

            if has_buildspec and overWrite:
                print("Replaced existing start.sh in ZIP.")
          
            else:
                print("Injected start.sh into ZIP.")
               # print(names)
        finally:
           
            if os.path.exists(tmp_zip_path):
                try:
                    os.remove(tmp_zip_path)
                except OSError:
                    pass
    
