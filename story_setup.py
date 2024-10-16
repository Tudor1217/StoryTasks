import argparse
import subprocess
import os

# Function to execute shell commands with optional sudo support
def run_command(cmd, sudo=False):
    try:
        if sudo:
            cmd = f"sudo {cmd}"  # Prepend 'sudo' if elevated permissions are needed
        result = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
        print(result.stdout)  # Output the result of the command
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}")
        print(e.output)  # Output any error that occurred during execution

# Step 1: Install necessary dependencies like curl, git, Go, and set up firewall rules
def install_dependencies():
    print("Installing dependencies...")
    run_command("apt update && apt install curl build-essential git wget jq make gcc tmux chrony -y", sudo=True)

    print("Configuring firewall to allow ports 26656 (Story) and 30303 (Story Geth)...")
    run_command("ufw allow to any port 26656", sudo=True)  # Allow Story's communication port
    run_command("ufw allow to any port 30303", sudo=True)  # Allow Story Geth's communication port
    run_command("ufw reload", sudo=True)  # Reload the firewall with new rules

# Step 2: Install the Go programming language, which is required for building Story and Story Geth binaries
def install_go(go_ver):
    print("Installing Go...")
    go_version = go_ver
    run_command(f"wget https://golang.org/dl/go{go_version}.linux-amd64.tar.gz")  # Download the specified Go version
    run_command(f"rm -rf /usr/local/go && tar -C /usr/local -xzf go{go_version}.linux-amd64.tar.gz", sudo=True)  # Install Go

    # Add Go binary path to user's profile for easier command execution
    go_env_cmd = 'export PATH=$PATH:/usr/local/go/bin'
    print("Adding Go binary to PATH...")
    with open(os.path.expanduser("~/.profile"), "a") as f:
        f.write(f"\n{go_env_cmd}\n")

    # Apply the updated Go environment path
    run_command(go_env_cmd)

# Step 3: Clone the Story and Story Geth repositories, then build the binaries
def clone_and_build(story_version, geth_version):
    print("Cloning Story repository and building binaries...")
    run_command("rm -rf story && git clone https://github.com/piplabs/story.git")  # Clone Story repo
    os.chdir("story")  # Enter the repository directory
    run_command(f"git checkout {story_version}")  # Checkout the specified Story version
    run_command("go build -o story ./client")  # Build Story binary
    run_command("cp ./story /usr/local/bin", sudo=True)  # Move binary to the system path

    print("Cloning Story Geth repository and building Story Geth binaries...")
    os.chdir("..")  # Navigate back to the parent directory
    run_command("rm -rf story-geth && git clone https://github.com/piplabs/story-geth.git")  # Clone Story Geth repo
    os.chdir("story-geth")  # Enter the Geth repo directory
    run_command(f"git checkout {geth_version}")  # Checkout the specified Geth version
    run_command("make geth")  # Build Geth binary
    run_command("sudo cp build/bin/geth /usr/local/bin", sudo=True)  # Move the Geth binary to system path

# Step 4: Create directories to store Story and Story Geth data
def create_data_directories():
    print("Creating directories for Story and Story Geth data...")
    story_dir = os.path.expanduser("~/.story/story")
    story_geth_dir = os.path.expanduser("~/.story/geth")

    os.makedirs(story_dir, exist_ok=True)  # Create Story data directory
    os.makedirs(story_geth_dir, exist_ok=True)  # Create Story Geth data directory

    print(f"Created Story data directory at: {story_dir}")
    print(f"Created Story Geth data directory at: {story_geth_dir}")

# Step 5: Initialize the Story node with a specified moniker
def initialize_node(moniker):
    print(f"Initializing the Story node with moniker '{moniker}'...")
    run_command(f"story init --moniker {moniker} --network iliad")  # Initialize Story node

# Step 6: Download the genesis and addrbook files for Story node setup
def download_genesis():
    print("Downloading genesis file and addrbook...")
    run_command("wget -O ~/.story/story/config/genesis.json https://snapshots.kjnodes.com/story-testnet/genesis.json")
    run_command("wget -O ~/.story/story/config/addrbook.json https://snapshots.kjnodes.com/story-testnet/addrbook.json")

# Step 7: Configure peers and seeds in the config.toml file for the Story node
def configure_peers():
    print("Configuring persistent peers and seeds...")
    seeds = "3f472746f46493309650e5a033076689996c8881@story-testnet.rpc.kjnodes.com:26659"
    peers = ""
    run_command(f"sed -i -e 's|^seeds *=.*|seeds = \"{seeds}\"|' ~/.story/story/config/config.toml")
    run_command(f"sed -i -e 's|^persistent_peers *=.*|persistent_peers = \"{peers}\"|' ~/.story/story/config/config.toml")

# Step 9: Enable Prometheus monitoring in the Story node configuration
def configure_gas_and_prometheus():
    print("Enabling Prometheus...")
    run_command("sed -i -e 's|^prometheus *=.*|prometheus = true|' ~/.story/story/config/config.toml")

# Step 10: Create a systemd service file to run Story and Story Geth nodes as background services
def create_service():
    print("Creating a systemd service file for the Story node and Story Geth...")

    service_file = """
[Unit]
Description=Geth Client
After=network.target

[Service]
User=root
Type=simple
ExecStart=/usr/local/bin/geth --iliad --syncmode full
Restart=on-failure
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
    """
    with open("/etc/systemd/system/geth.service", "w") as f:
        f.write(service_file)  # Write the systemd service file for Geth

    run_command("sudo systemctl daemon-reload", sudo=True)
    run_command("sudo systemctl enable geth", sudo=True)
    run_command("sudo systemctl start geth", sudo=True)

    service_file = """
[Unit]
Description=Story Validator
After=network.target

[Service]
User=root
Type=simple
ExecStart=/usr/local/bin/story run
Restart=on-failure
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
    """
    with open("/etc/systemd/system/story.service", "w") as f:
        f.write(service_file)  # Write the systemd service file for Story

    run_command("sudo systemctl daemon-reload", sudo=True)
    run_command("sudo systemctl enable story", sudo=True)
    run_command("sudo systemctl start story", sudo=True)

# Step 11: Set up snapshot synchronization for both Story and Geth nodes
def setup_snapshot():
    print("Setting up snapshot...")

    run_command("sudo systemctl stop geth", sudo=True)  # Stop Geth node
    run_command("sudo systemctl stop story", sudo=True)  # Stop Story node

    # Download and restore the Geth snapshot
    run_command("rm -rf ~/.story/geth/iliad/geth/chaindata")
    run_command("curl -L https://snapshots.kjnodes.com/story-testnet/snapshot_latest_geth.tar.lz4 | tar -Ilz4 -xf - -C $HOME/.story/geth")
    run_command("sudo systemctl restart geth", sudo=True)

    # Download and restore the Story snapshot
    run_command("rm -rf ~/.story/story/data")
    run_command("curl -L https://snapshots.kjnodes.com/story-testnet/snapshot_latest.tar.lz4 | tar -Ilz4 -xf - -C $HOME/.story/story")
    run_command("sudo systemctl restart story", sudo=True)

# Step 12: Check and verify logs of the Story service for troubleshooting
def verify_logs():
    print("Verifying logs...")
    run_command("sudo journalctl -u story -f --no-hostname -o cat", sudo=True)

# Additional Functions for Node Control:
# Function to start the Story and Geth nodes
def start_node():
    print("Starting Story node...")
    run_command("sudo systemctl start geth", sudo=True)
    run_command("sudo systemctl start story", sudo=True)

# Function to stop the Story and Geth nodes
def stop_node():
    print("Stopping Story node...")
    run_command("sudo systemctl stop geth", sudo=True)
    run_command("sudo systemctl stop story", sudo=True)

# Function to check the status of Story and Geth nodes
def node_status():
    print("Checking Story node status...")
    run_command("sudo systemctl status geth", sudo=True)
    run_command("sudo systemctl status story", sudo=True)

# Function to update the Story node binary
def update_node():
    print("Updating Story node...")
    run_command("sudo systemctl stop story", sudo=True)
    run_command("story version")  # Check current Story version
    print("Cloning Story repository and building binaries...")
    run_command("rm -rf story && git clone https://github.com/piplabs/story.git")
    os.chdir("story")
    run_command("make build")  # Rebuild Story binary
    run_command("sudo cp build/story /usr/local/bin", sudo=True)
    run_command("story version")  # Check updated Story version
    run_command("sudo systemctl start story", sudo=True)

# Function to check the synchronization status of the Story node
def sync_status():
    print("Checking Story node sync status...")
    run_command("story status | jq .SyncInfo")  # Check sync status using jq

# Main function to parse command-line arguments and perform actions based on user input
def main():
    parser = argparse.ArgumentParser(description="Manage and install a Story node.")

    # Define command-line arguments for each step or action
    parser.add_argument("action", choices=[
        "install_dependencies", "install_go", "clone_and_build",
        "create_data_directories", "initialize_node", "download_genesis",
        "configure_peers", "configure_gas_and_prometheus",
        "create_service", "setup_snapshot", "verify_logs", "full_install",
        "start_node", "stop_node", "node_status", "update_node", "sync_status"
    ], help="Action to perform")

    # Optional arguments for moniker, versions, etc.
    parser.add_argument("--moniker", help="Node's moniker (required for initialization and configuration)", default="StoryNode", dest="moniker")
    parser.add_argument("--tcp-port", help="Node's tcp-port (required for configuration)", default="26657", dest="tcp_port")
    parser.add_argument("--story-version", help="Story version", default="v0.11.0", dest="story_version")
    parser.add_argument("--geth-version", help="Geth version", default="v0.9.3", dest="geth_version")
    parser.add_argument("--go-version", help="Go version", default="1.22.8", dest="go_version")

    args = parser.parse_args()

    # Call the appropriate function based on the specified action
    if args.action == "install_dependencies":
        install_dependencies()
    elif args.action == "install_go":
        install_go(args.go_version)
    elif args.action == "clone_and_build":
        clone_and_build(args.story_version, args.geth_version)
    elif args.action == "create_data_directories":
        create_data_directories()
    elif args.action == "initialize_node":
        initialize_node(args.moniker)
    elif args.action == "download_genesis":
        download_genesis()
    elif args.action == "configure_peers":
        configure_peers()
    elif args.action == "configure_gas_and_prometheus":
        configure_gas_and_prometheus()
    elif args.action == "create_service":
        create_service()
    elif args.action == "setup_snapshot":
        setup_snapshot()
    elif args.action == "verify_logs":
        verify_logs()
    elif args.action == "full_install":
        # Full installation sequence
        install_dependencies()
        install_go(args.go_version)
        clone_and_build(args.story_version, args.geth_version)
        create_data_directories()
        initialize_node(args.moniker)
        configure_gas_and_prometheus()
        create_service()
        setup_snapshot()
    elif args.action == "start_node":
        start_node()
    elif args.action == "stop_node":
        stop_node()
    elif args.action == "node_status":
        node_status()
    elif args.action == "update_node":
        update_node()
    elif args.action == "sync_status":
        sync_status()

if __name__ == "__main__":
    main()
