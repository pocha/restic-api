## Create Linux Binary

To create `restic-api-linux`, install `pyinstaller` as `pip install pyinstaller` & then run following commands

```
pyinstaller --onefile --add-data 'basic-web-ui:basic-web-ui' --add-data 'restic_installer_scripts:restic_installer_scripts' main.py
``` 

It will create `main` exectuable in `dist/` folder. Rename it to restic-api-linux. 

## Windows Installer zip

> ToDo - create windows binary using pyinstaller on windows 

Run `create-installer.sh` on linux machine. It will pick relevant python & web files from the main directory, picks the `.bat` files from this directory & create a zip in `install` directory 
