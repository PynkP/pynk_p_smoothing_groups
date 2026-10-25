# pynk_p Smoothing Groups — 1.0.0

Created by **pynk_p**

An add-on for **Blender 5.2.3 LTS** providing 3ds Max–style **30 Smoothing Groups**, angle-based auto-assignment, and non-destructive **Subdivision by Smoothing Groups** using Geometry Nodes.

The UI appears in the 3D Viewport Sidebar (`N` panel) under the **`pynk_p`** tab with two panels:
- `Smoothing Groups`
- `Subdivision By Smoothing Groups`

> 한국어 문서는 [README_KO.md](README_KO.md)를 참고하세요.

### 📦 [Download Latest Release (`pynkp_smoothing_groups-1.0.0.zip`)](https://github.com/PynkP/pynk_p_smoothing_groups/releases/latest)

---

## Features

- **30 Smoothing Groups (Bitmask-based)**: Assign multiple overlapping smoothing groups per face (`1`–`30`).
- **Union Selection Display**: The grid highlights the union of all groups present on the current face selection. Clicking an active group removes it from all selected faces; clicking an inactive group adds it to all selected faces.
- **Auto Smooth by Angle**: Automatically assigns smoothing groups to selected faces based on an angle threshold (default `30°`) while respecting unselected neighbor boundaries.
- **Select by Group**: Quickly select visible faces belonging to a specific smoothing group.
- **Subdivision By Smoothing Groups**: Non-destructively preserves hard edges between faces that do not share a smoothing group during Subdivision Surface evaluation while preserving user-authored edge creases (`max(user_crease, group_boundary)`).
- **Non-Destructive Workflow**: Uses Geometry Nodes modifiers (`Set Mesh Normal` and boundary crease evaluation) without overwriting your base mesh's `sharp_edge`, `crease_edge`, or custom split normals. Saved `.blend` files retain their shading even if the add-on is disabled.

---

## Installation

1. Download the extension `.zip` package (do not unzip it).
2. In Blender, open `Edit > Preferences > Get Extensions` (or `Add-ons`).
3. Click the top-right dropdown menu and choose **`Install from Disk...`**, then select the `.zip` file.
4. Ensure **`pynk_p Smoothing Groups`** is enabled.
5. Select a mesh object and press `N` in the 3D Viewport to open the **`pynk_p`** sidebar tab.

---

## Usage

### 1. Manual Group Assignment
1. Select a mesh object and enter **Edit Mode** (`Tab`) with Face Select enabled.
2. Select one or more faces.
3. Click numbers `1`–`30` in the **`Smoothing Groups`** panel:
   - **Active button clicked**: Removes that group from all selected faces.
   - **Inactive button clicked**: Adds that group to all selected faces.
   - **`Clear Groups`**: Clears all smoothing groups from the selected faces (ungrouped faces shade flat).
   - **`Group` + `Select`**: Replaces the current visible face selection with faces belonging to the specified group number.

### 2. Auto Smooth by Angle
1. In Edit Mode, select the faces you want to classify (select all faces to classify the entire mesh).
2. Set the **`Angle`** threshold (default `30°`).
3. Click **`Auto Smooth`**.

### 3. Subdivision By Smoothing Groups
1. Assign smoothing groups to your mesh first.
2. In the **`Subdivision By Smoothing Groups`** panel, click **`Add Subdivision`**.
3. Adjust **`Viewport Levels`** and **`Render Levels`**.
4. Toggle **`Use Smoothing Groups`** to compare subdivision with and without smoothing-group boundary creases.
5. Click **`Remove SG Subdivision`** to remove the managed subdivision and boundary modifiers while keeping your smoothing group assignments intact.

### 4. Updating After Mesh Edits
Group button actions update normals and boundaries immediately. After topology or geometry edits (such as moving vertices, Extrude, Bevel, or Merge), click **`Update Boundaries`** to recalculate group normals and boundary creases.

---

## License

This project is licensed under the **GNU General Public License v3.0 or later (`GPL-3.0-or-later`)**. See [LICENSE.txt](LICENSE.txt) for details.
