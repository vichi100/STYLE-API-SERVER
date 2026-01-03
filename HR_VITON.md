# HR-VITON Weights Setup

The automatic download failed because verified public Mirrors for HR-VITON weights are gated or removed.
You need to manually upload the weights to your Modal Volume.

## Step 1: Download Weights
Download the official weights from the [HR-VITON GitHub](https://github.com/sangyun87/HR-VITON) (check the "Data Preparation" section for Google Drive links).

You typically need:
- `alias_final.pth` (or `mtviton.pth`)
- `segment_final.pth` (or `gen.pth`)
- `G_final.pth`

## Step 2: Upload to Modal Volume
Run these commands in your terminal (adjust local paths):

```bash
modal volume put hr-viton-weights /path/to/local/alias_final.pth /weights/alias_final.pth
modal volume put hr-viton-weights /path/to/local/segment_final.pth /weights/segment_final.pth
modal volume put hr-viton-weights /path/to/local/G_final.pth /weights/G_final.pth
```

## Step 3: Verify
Run a shell to check files:

```bash
modal volume shell hr-viton-weights
> ls -l /weights
```
