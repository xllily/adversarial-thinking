# Vendor webhook cutover

The cutover is reversible for 24 hours. Its only irreversible step is deleting
the old webhook secret after the production vendor endpoint has been observed
signing `X-Vendor-Signature-V3` on three consecutive deliveries.

No production request may be sent from this workspace. The current task is to
decide whether the irreversible step is ready now.
