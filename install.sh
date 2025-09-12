#! /bin/bash

cd "$(dirname "$0")" # cd to the directory of this script
abs_path=`pwd`


create_systemd_service() {
  if [ ! -d /etc/systemd/system ]; then
    echo "Systemd not found. This script is only for systemd based systems."
    exit 1
  fi

  echo "Creating systemd service at /etc/systemd/system/restic-api.service"

  sudo tee /etc/systemd/system/restic-api.service > /dev/null <<- EOM
[Unit]
Description=Restic API Service
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
ExecStart=${abs_path}/start_server.sh > ~/.restic-api/server.logs 2>&1
ExecStop=kill -9 \`ps -ef | grep "python main.py" | head -n 1 | awk '{print $2}'\`

[Install]
WantedBy=multi-user.target
EOM

  echo "Reloading systemd daemon"
  sudo systemctl daemon-reload
}



OS=$(uname -s)
if [ "$OS" = "Darwin" ]; then
  echo "Mac OS installation is not yet supported"
  #install_unix
  #create_launchd_plist
  #enable_launchd_plist
  #sudo xattr -d com.apple.quarantine /usr/local/bin/backrest # remove quarantine flag
elif [ "$OS" = "Linux" ]; then
  
  which python3
  if [ $? == 1 ]
  then
    echo "Install Python (Python3 to be specific) first & re-run the script"
    exit 1
  fi
  echo "Cool .. found Python .. we are good"
  
  restic version
  if [ $? == 1 ]
  then
    echo "Install restic from https://github.com/restic/restic/releases"
    exit 1
  fi
  echo "Cool restic also found .. this is amazing :)"

  echo "Installing Restic API on Linux"
  create_systemd_service
  echo "Enabling systemd service restic-api.service"
  sudo systemctl enable restic-api
  sudo systemctl start restic-api
else
  echo "Unknown OS: $OS. This script only supports Darwin and Linux."
  exit 1
fi

echo "Restic API now accessible at http://<ip of this machine>:5000"