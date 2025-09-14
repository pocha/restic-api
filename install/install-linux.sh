#! /bin/bash

cd "$(dirname "$0")" # cd to the directory of this script


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
ExecStart=/usr/local/bin/restic-api  > ~/.restic-api/server.logs 2>&1
ExecStop=kill -9 \`ps -ef | grep restic-api | head -n 1 | awk '{print $2}'\`

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
  
  restic version
  if [ $? == 1 ]
  then
    echo "Install restic from https://github.com/restic/restic/releases"
    exit 1
  fi
  echo "Cool restic also found .. this is amazing :)"

  echo "Installing Restic API on Linux"
  sudo cp restic-api-linux /usr/local/bin/restic-api

  create_systemd_service
  echo "Enabling systemd service restic-api.service"
  sudo systemctl enable restic-api
  sudo systemctl start restic-api
else
  echo "Unknown OS: $OS. This script only supports Darwin and Linux."
  exit 1
fi

echo "Restic API now accessible at http://<ip of this machine>:5000"
