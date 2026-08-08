An tool that provides a few tools to assist in recovery of data inside of 
CMD (Creative Micro Designs) images

Supports D2M, D4M, DHD and DNP images
This is not fully tested, consider it in BETA. Before attempting to use this tool,
please make a backup of the image file just in case.

Features:
  Import and Export of the partition tables for D2M, D4M and DHD images
  A partition detection scanner: Will scan the selected image for 1541, 1571, 1581,
  and Native partitions, and then over-write the partition table with the partitions
  that were successfully located.

  Also a scanner for DNP images to attempt to locate missing files and subdirectories.
