import os
import moondream as md
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    api_key = os.getenv("MOONDREAM_API_KEY")
    if not api_key:
        print("❌ Error: MOONDREAM_API_KEY not found in .env")
        return

    # Initialize client
    try:
        model = md.vl(api_key=api_key)
    except Exception as e:
        print(f"❌ Error initializing Moondream client: {e}")
        return

    # Load image
    image_path = "red-dress.jpg"; #"redshorts.png" # Using the existing test image
    if not os.path.exists(image_path):
        print(f"❌ Error: Image {image_path} not found.")
        return

    print(f"Analyzing {image_path} with Moondream SDK...")
    image = Image.open(image_path)
    
    # 0. General Caption
    print("\n--- Generating Caption ---")
    try:
        caption = model.caption(image)
        # Check if caption is a dict or string based on SDK return
        if isinstance(caption, dict) and 'caption' in caption:
             print(f"Caption: {caption['caption']}")
        else:
             print(f"Caption: {caption}")
    except Exception as e:
        print(f"Error generating caption: {e}")

    # 1. Identify Objects (Query)
    print("\n--- Identifying Objects ---")
    try:
        # Ask the model to list objects
        question = "List the main clothing items and objects visible in this image, separated by commas."
        answer_data = model.query(image, question)
        
        # Parse answer (handle dict return)
        answer = answer_data['answer'] if isinstance(answer_data, dict) else answer_data
        print(f"Model Identified: {answer}")
        
        # Split into list
        detected_objects = [obj.strip() for obj in answer.split(',')]
        
    except Exception as e:
        print(f"Error identifying objects: {e}")
        detected_objects = ["shorts", "shirt"] # Fallback

    # 2. Point-Guided Segmentation
    print(f"\n--- Processing Objects (Point -> Segment) ---")
    for target_object in detected_objects:
        if not target_object: continue
        
        print(f"\n> Processing: '{target_object}'")
        
        try:
            # Step A: Get Points
            print(f"  [Point] Finding points for '{target_object}'...")
            point_result = model.point(image, target_object)
            points = point_result["points"]
            print(f"  Found {len(points)} point(s): {points}")
            
            if not points:
                print("  No points found, skipping segmentation.")
                continue

            # Step B: Segment using Points
            # We will use ALL points found for the object as spatial references
            spatial_refs = [[p['x'], p['y']] for p in points]
            
            # DEBUG: Draw points on image
            try:
                from PIL import ImageDraw
                debug_img = image.copy()
                draw = ImageDraw.Draw(debug_img)
                w, h = debug_img.size
                for sr in spatial_refs:
                    # Draw a red circle at the point
                    px, py = sr[0] * w, sr[1] * h
                    r = 10
                    draw.ellipse((px-r, py-r, px+r, py+r), fill="red", outline="white")
                
                debug_filename = f"debug_point_{target_object.replace(' ', '_').replace('/', '_')}.png"
                debug_img.save(debug_filename)
                print(f"  [Debug] Saved point visualization to: {debug_filename}")
            except Exception as e:
                print(f"  [Debug] Failed to draw points: {e}")

            print(f"  [Segmentation] Segmenting '{target_object}' with spatial_refs={spatial_refs}...")
            seg_result = model.segment(image, target_object, spatial_refs=spatial_refs)
            
            # DEBUG: Print full keys and raw path stats
            print(f"  [Debug] Seg result keys: {seg_result.keys()}")
            if 'bbox' in seg_result:
                print(f"  [Debug] Seg raw bbox: {seg_result['bbox']}")
            
            if 'path' in seg_result:
                path_str = seg_result['path']
                
                # Rasterize Path
                try:
                    import numpy as np
                    from svgpath2mpl import parse_path
                    from matplotlib.path import Path
                    
                    # 1. Parse SVG Path
                    mpl_path = parse_path(path_str)
                    
                    # 2. Get Bounding Box for Scaling
                    # The path coordinates are normalized (0-1) relative to this BBOX, not the full image.
                    if 'bbox' in seg_result:
                        bbox = seg_result['bbox']
                        x_min = bbox['x_min']
                        y_min = bbox['y_min']
                        x_max = bbox['x_max']
                        y_max = bbox['y_max']
                    else:
                        # Fallback to 0-1 if bbox missing (unlikely for valid result)
                        x_min, y_min, x_max, y_max = 0.0, 0.0, 1.0, 1.0
                        print("  [Warning] No bbox in seg result, assuming full image relative path.")

                    # Calculate bbox dimensions in pixels
                    img_w, img_h = image.size
                    box_w_px = (x_max - x_min) * img_w
                    box_h_px = (y_max - y_min) * img_h
                    box_x_px = x_min * img_w
                    box_y_px = y_min * img_h
                    
                    # 3. Transform Vertices
                    # path_x * box_width + box_x_start
                    vertices = mpl_path.vertices.copy()
                    vertices[:, 0] = (vertices[:, 0] * box_w_px) + box_x_px
                    vertices[:, 1] = (vertices[:, 1] * box_h_px) + box_y_px
                    
                    # Create scaled path
                    scaled_path = Path(vertices, mpl_path.codes)
                    
                    # 4. Create Grid of Points
                    x, y = np.meshgrid(np.arange(image.width), np.arange(image.height))
                    points_grid = np.vstack((x.flatten(), y.flatten())).T
                    
                    # 5. Check which points are inside the path
                    mask_flat = scaled_path.contains_points(points_grid)
                    mask = mask_flat.reshape(image.height, image.width)
                    
                    # 6. Create Alpha Mask Image
                    mask_img = Image.fromarray((mask * 255).astype(np.uint8), mode='L')
                    
                    # DEBUG: Save raw mask
                    mask_debug_name = f"debug_mask_{target_object.replace(' ', '_').replace('/', '_')}.png"
                    mask_img.save(mask_debug_name)
                    print(f"  [Debug] Saved raw mask to: {mask_debug_name}")
                    
                    # 7. Apply to Original Image
                    segmented_img = image.convert("RGBA")
                    segmented_img.putalpha(mask_img)
                    
                    # 8. Crop to Bounding Box
                    # Now that the mask is correctly placed, cropping to the mask's bbox should work perfectly.
                    bbox = mask_img.getbbox()
                    if bbox:
                        segmented_img = segmented_img.crop(bbox)
                    
                    item_name = target_object.replace(" ", "_").replace('/', '_').lower()
                    filename = f"segmented_{item_name}_refined.png"
                    segmented_img.save(filename)
                    print(f"    -> Saved refined segmented image to: {filename}")
                    
                except ImportError as ie:
                     print(f"  [Segmentation] Missing libraries: {ie}")
                except Exception as ex:
                     print(f"  [Segmentation] Rasterization failed: {ex}")

            else:
                print("  No 'path' found in segmentation result.")
                
        except Exception as e:
            print(f"  [Error] Processing failed: {e}")

if __name__ == "__main__":
    main()
