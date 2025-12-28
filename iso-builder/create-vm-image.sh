#!/bin/bash
#
# OLT Manager VM Image Creator
# Creates a QCOW2 virtual machine image ready to deploy
# NOTE: Must run on a system with full privileges (not in a container)
#

set -e

VERSION=$(cat /root/olt-manager/backend/VERSION 2>/dev/null || echo "1.0.0")
OUTPUT_DIR="/root/olt-manager/iso-builder/output"
WORK_DIR="/tmp/olt-vm-build"
IMAGE_NAME="olt-manager-appliance-${VERSION}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[*]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[X]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          OLT Manager VM Image Creator                        ║"
echo "║                    Version $VERSION                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    exit 1
fi

# Check if we can use mknod
if ! mknod -m 666 /tmp/test-mknod-$$ c 1 3 2>/dev/null; then
    print_error "This script requires full system privileges."
    print_error "Please run on a bare-metal or VM system, not in a container."
    rm -f /tmp/test-mknod-$$ 2>/dev/null
    exit 1
fi
rm -f /tmp/test-mknod-$$

# Install required tools
print_status "Installing required tools..."
apt-get update -qq
apt-get install -y -qq qemu-utils cloud-image-utils wget genisoimage

# Create directories
mkdir -p "$WORK_DIR" "$OUTPUT_DIR"

# Download Ubuntu cloud image
CLOUD_IMAGE_URL="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
CLOUD_IMAGE="$WORK_DIR/ubuntu-cloud.img"

if [[ ! -f "$CLOUD_IMAGE" ]]; then
    print_status "Downloading Ubuntu cloud image..."
    wget -q --show-progress -O "$CLOUD_IMAGE" "$CLOUD_IMAGE_URL"
fi

# Create the VM image
print_status "Creating VM image..."
FINAL_IMAGE="$OUTPUT_DIR/${IMAGE_NAME}.qcow2"
cp "$CLOUD_IMAGE" "$FINAL_IMAGE"

# Resize to 10GB
qemu-img resize "$FINAL_IMAGE" 10G

# Create cloud-init configuration
print_status "Creating cloud-init configuration..."

mkdir -p "$WORK_DIR/cloud-init"

# Create user-data
cat > "$WORK_DIR/cloud-init/user-data" << 'EOF'
#cloud-config
hostname: olt-manager
users:
  - name: root
    lock_passwd: false
    hashed_passwd: $6$rounds=4096$xyz$hash
    shell: /bin/bash

package_update: true
package_upgrade: true

packages:
  - python3
  - python3-pip
  - python3-venv
  - nginx
  - snmp
  - snmp-mibs-downloader
  - curl
  - wget
  - net-tools
  - openssh-server
  - sshpass

write_files:
  - path: /tmp/setup-olt.sh
    permissions: '0755'
    content: |
      #!/bin/bash
      export DEBIAN_FRONTEND=noninteractive

      # Download and install OLT Manager
      cd /tmp
      wget -q http://lic.proxpanel.com/downloads/olt-manager-installer-latest.run
      bash olt-manager-installer-latest.run

      # Setup complete
      touch /etc/olt-manager/.setup_done

runcmd:
  - bash /tmp/setup-olt.sh

final_message: "OLT Manager Appliance is ready!"
EOF

# Create meta-data
cat > "$WORK_DIR/cloud-init/meta-data" << EOF
instance-id: olt-manager-appliance
local-hostname: olt-manager
EOF

# Create cloud-init ISO
print_status "Creating cloud-init ISO..."
genisoimage -output "$WORK_DIR/cloud-init.iso" -volid cidata -joliet -rock \
    "$WORK_DIR/cloud-init/user-data" "$WORK_DIR/cloud-init/meta-data" 2>/dev/null

# Merge cloud-init into image
print_status "Configuring VM image..."
# Note: This is a basic image - user needs to attach cloud-init ISO on first boot
# or use virt-customize for more advanced customization

cp "$WORK_DIR/cloud-init.iso" "$OUTPUT_DIR/${IMAGE_NAME}-cloud-init.iso"

# Create OVA wrapper
print_status "Creating OVA package..."

mkdir -p "$WORK_DIR/ova"

# Convert to VMDK for VMware compatibility
qemu-img convert -f qcow2 -O vmdk "$FINAL_IMAGE" "$WORK_DIR/ova/${IMAGE_NAME}.vmdk"

# Create OVF descriptor
cat > "$WORK_DIR/ova/${IMAGE_NAME}.ovf" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<Envelope xmlns="http://schemas.dmtf.org/ovf/envelope/1" xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <References>
    <File ovf:href="${IMAGE_NAME}.vmdk" ovf:id="file1"/>
  </References>
  <DiskSection>
    <Info>Virtual disk information</Info>
    <Disk ovf:capacity="10737418240" ovf:diskId="vmdisk1" ovf:fileRef="file1" ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
  </DiskSection>
  <NetworkSection>
    <Info>Network info</Info>
    <Network ovf:name="VM Network">
      <Description>VM Network</Description>
    </Network>
  </NetworkSection>
  <VirtualSystem ovf:id="OLT-Manager-Appliance">
    <Info>OLT Manager Appliance</Info>
    <Name>OLT Manager Appliance ${VERSION}</Name>
    <OperatingSystemSection ovf:id="96">
      <Info>Ubuntu 64-bit</Info>
    </OperatingSystemSection>
    <VirtualHardwareSection>
      <Info>Virtual hardware requirements</Info>
      <System>
        <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
        <vssd:InstanceID>0</vssd:InstanceID>
        <vssd:VirtualSystemType>vmx-13</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:Description>Number of Virtual CPUs</rasd:Description>
        <rasd:ElementName>2 virtual CPU(s)</rasd:ElementName>
        <rasd:InstanceID>1</rasd:InstanceID>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>2</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:AllocationUnits>MegaBytes</rasd:AllocationUnits>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:ElementName>2048MB of memory</rasd:ElementName>
        <rasd:InstanceID>2</rasd:InstanceID>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:VirtualQuantity>2048</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
        <rasd:ElementName>Hard Disk 1</rasd:ElementName>
        <rasd:HostResource>ovf:/disk/vmdisk1</rasd:HostResource>
        <rasd:InstanceID>3</rasd:InstanceID>
        <rasd:Parent>4</rasd:Parent>
        <rasd:ResourceType>17</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>VM Network</rasd:Connection>
        <rasd:ElementName>Ethernet adapter on VM Network</rasd:ElementName>
        <rasd:InstanceID>5</rasd:InstanceID>
        <rasd:ResourceSubType>VmxNet3</rasd:ResourceSubType>
        <rasd:ResourceType>10</rasd:ResourceType>
      </Item>
    </VirtualHardwareSection>
  </VirtualSystem>
</Envelope>
EOF

# Create OVA (tar archive)
cd "$WORK_DIR/ova"
tar -cvf "$OUTPUT_DIR/${IMAGE_NAME}.ova" "${IMAGE_NAME}.ovf" "${IMAGE_NAME}.vmdk"

# Cleanup
print_status "Cleaning up..."
rm -rf "$WORK_DIR"

# Show results
QCOW2_SIZE=$(du -h "$FINAL_IMAGE" | cut -f1)
OVA_SIZE=$(du -h "$OUTPUT_DIR/${IMAGE_NAME}.ova" | cut -f1)

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                 VM Images Created!                           ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  QCOW2 (KVM/Proxmox): $FINAL_IMAGE"
echo "║  Size: $QCOW2_SIZE"
echo "║                                                              ║"
echo "║  OVA (VMware/VirtualBox): $OUTPUT_DIR/${IMAGE_NAME}.ova"
echo "║  Size: $OVA_SIZE"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
