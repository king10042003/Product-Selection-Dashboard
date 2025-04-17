from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
import os
import pandas as pd
import csv
import json

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Use a secure key in production

# Define folder paths relative to app.py
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
SAMPLE_CSV_PATH = os.path.join(os.getcwd(), "static", "sample.csv")
SELECTED_CSV_PATH = os.path.join(os.getcwd(), "static", "selected_products.csv")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure required directories exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(os.path.join(os.getcwd(), "static")):
    os.makedirs(os.path.join(os.getcwd(), "static"))

# Automatically generate sample CSV if not exists (without IMAGE column)
def create_sample_csv():
    if not os.path.exists(SAMPLE_CSV_PATH):
        with open(SAMPLE_CSV_PATH, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Item Code", "AG", "Unit Weight", "Complexity Code", "Product Group", "Stock Value", "Product Category Description"])
            writer.writerow(["P0012345", "L001", "10", "High", "Group A", "500", "Category 1"])
            writer.writerow(["P0026789", "L002", "20", "Medium", "Group B", "700", "Category 2"])

create_sample_csv()

# Route: Index / Upload Page
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["file"]
        if file and file.filename:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            # Read CSV and process IMAGE column
            df = pd.read_csv(filepath, dtype=str)

            # Safe helper function for image URL generation
            def generate_image_url(x):
                try:
                    if pd.isna(x):
                        return ""
                    x_str = str(x).split(".")[0]  # remove decimal part
                    if len(x_str) >= 9:
                        return f"https://jewbridge.titanjew.in/CatalogImages/api/ImageFetch/?Type=ProductImages&ImageName={x_str[2:9]}.jpg"
                    return ""
                except Exception:
                    return ""

            # Add IMAGE column if "Item Code" is present
            if "Item Code" in df.columns:
                df["IMAGE"] = df["Item Code"].apply(generate_image_url)

            # Save updated CSV
            df.to_csv(filepath, index=False)

            # Update session
            session["uploaded_file"] = filepath
            session["selected_items"] = []
            session["total_rows"] = len(df)

            return redirect(url_for("dashboard"))

    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    file_path = session.get("uploaded_file")
    if not file_path or not os.path.exists(file_path):
        return redirect(url_for("index"))

    # Pagination setup
    page = int(request.args.get("page", 1))
    per_page = 21

    # Load full dataframe
    full_df = pd.read_csv(file_path, dtype=str)

    # Add IMAGE column if not present
    if "Item Code" in full_df.columns and "IMAGE" not in full_df.columns:
        def generate_image_url(x):
            try:
                if pd.isna(x):
                    return ""
                x_str = str(x).split(".")[0]
                return (
                    f"https://jewbridge.titanjew.in/CatalogImages/api/ImageFetch/?Type=ProductImages&ImageName={x_str[2:9]}.jpg"
                    if len(x_str) >= 9 else ""
                )
            except:
                return ""
        full_df["IMAGE"] = full_df["Item Code"].apply(generate_image_url)

    # Get selected items from session
    selected_items = session.get("selected_items", [])

    # Filtered DataFrame for viewing
    df = full_df.copy()
    filter_col = request.args.get("filter_col")
    filter_val = request.args.get("filter_val")

    if filter_col and filter_val:
        filter_col = filter_col.strip()
        filter_values = [val.strip() for val in filter_val.split(",")]
        if filter_col in df.columns:
            df = df[df[filter_col].isin(filter_values)]

    # Create paginated data
    total_pages = (len(df) + per_page - 1) // per_page
    paginated_df = df.iloc[(page - 1) * per_page: page * per_page]

    # Mark items on current page as selected (used in frontend to check checkboxes)
    paginated_data = paginated_df.to_dict(orient="records")
    for item in paginated_data:
        item["is_selected"] = item.get("Item Code") in selected_items

    selected_items_all_pages = []

    # Assuming `selected_items` is the list of items selected on the current page:
    selected_items_all_pages.extend(selected_items)

    # Create the DataFrame based on selected items across all pages
    selected_df = full_df[full_df["Item Code"].isin(selected_items_all_pages)] if "Item Code" in full_df.columns else pd.DataFrame()

    # If 'AG' column exists, proceed with counting the 'AG' values
    if "AG" in selected_df.columns:
        selected_df["AG"].fillna("Other", inplace=True)
        ag_summary = selected_df["AG"].value_counts().reset_index()
        ag_summary.columns = ['AG', 'Count']
    else:
        ag_summary = pd.DataFrame(columns=['AG', 'Count'])

    # Now ag_summary will hold the 'AG' counts across all selected items

    # Dropdown filter column list
    column_data = [col for col in df.columns if col not in ["IMAGE", "Sno."]]

    return render_template(
        "dashboard.html",
        data=paginated_data,
        total_pages=total_pages,
        current_page=page,
        selected_items=selected_items,
        column_data=column_data,
        ag_summary=ag_summary
    )









@app.route("/download_sample")
def download_sample():
    return send_file(SAMPLE_CSV_PATH, as_attachment=True)

# Route: Save selection via AJAX (stores list of selected Item Codes in session)
@app.route("/save_selection", methods=["POST"])
def save_selection():
    try:
        selected_items = request.json.get("selected", [])
        session["selected_items"] = selected_items
        selected_count= len(selected_items)
        session.modified = True
        return jsonify({"message": "Selection saved successfully","selectedCount": selected_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Route: Download Selected Products CSV (exports all selected rows)
@app.route("/download_selected")
def download_selected():
    # Generate the image URL based on the item code
    def generate_image_url(x):
        """
        Generate the image URL based on the item code.
        The image URL is constructed by extracting a part of the item code.
        """
        try:
            if pd.isna(x):
                return ""  # If the value is NaN, return an empty string

            x_str = str(x).split(".")[0]  # Remove the decimal part (if any)

            # Ensure the item code has sufficient length to extract a part of it
            if len(x_str) >= 9:
                return f"https://jewbridge.titanjew.in/CatalogImages/api/ImageFetch/?Type=ProductImages&ImageName={x_str[2:9]}.jpg"

            return ""  # Return empty if the length is insufficient
        except Exception:
            return ""  # Return empty in case of any error

    # Get selected items and uploaded file path from the session
    selected_items = session.get("selected_items", [])
    file_path = session.get("uploaded_file")
    
    # Check if there are selected items and if the file path is valid
    if not selected_items or not file_path:
        return "No items selected or file path missing", 400
    
    # Ensure the file exists
    if not os.path.exists(file_path):
        return "Uploaded file not found", 404
    
    try:
        # Load the CSV file
        df = pd.read_csv(file_path, dtype=str)
        
        # Check if "Item Code" column exists
        if "Item Code" not in df.columns:
            return "Item Code column not found in CSV", 400
        
        # Add the "IMAGE" column by applying the generate_image_url function
        df["IMAGE"] = df["Item Code"].apply(generate_image_url)
        
        # Filter the selected items
        selected_df = df[df["Item Code"].isin(selected_items)]
        
        # Check if any selected items are found
        if selected_df.empty:
            return "No matching items found in the uploaded file", 404
        
        # Save the filtered data to a CSV file
        selected_df.to_csv(SELECTED_CSV_PATH, index=False)
        
        # Send the generated CSV file as a downloadable attachment
        return send_file(SELECTED_CSV_PATH, as_attachment=True)
    
    except Exception as e:
        return f"An error occurred: {str(e)}", 500
    


@app.route("/get_unique_values")
def get_unique_values():
    file_path = session.get("uploaded_file")
    column = request.args.get("column")

    if not file_path or not column:
        return jsonify({"values": []})

    # Check if file exists
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 400

    try:
        df = pd.read_csv(file_path, dtype=str)
    except Exception as e:
        return jsonify({"error": f"Error reading CSV: {str(e)}"}), 500

    if column in df.columns:
        unique_vals = df[column].dropna().unique().tolist()
        print(f"Unique values for {column}: {unique_vals}")  # Debugging line
        return jsonify({"values": unique_vals})
    else:
        return jsonify({"values": []})


# Add this new route to your app.py
@app.route("/get_selected_ag_data")
def get_selected_ag_data():
    try:
        file_path = session.get("uploaded_file")
        selected_items = session.get("selected_items", [])
        if not selected_items:
            return jsonify({"ag_counts": {}, "item_to_ag": {}})

        if not file_path or not os.path.exists(file_path):
            return jsonify({"ag_data": {}})

        # Load the complete dataframe
        df = pd.read_csv(file_path, dtype=str)

        # Filter to only selected items (copy to avoid SettingWithCopyWarning)
        selected_df = df[df["Item Code"].isin(selected_items)].copy()

        # Extract AG and Item Code pairs
        if "AG" in selected_df.columns:
            # Fill NA values with "Unknown"
            selected_df["AG"] = selected_df["AG"].fillna("Unknown")

            # Get counts by AG
            ag_counts = selected_df["AG"].value_counts().to_dict()

            # Map Item Code to AG
            item_to_ag = selected_df.set_index("Item Code")["AG"].to_dict()

            return jsonify({
                "ag_counts": ag_counts,
                "item_to_ag": item_to_ag
            })
        else:
            return jsonify({"ag_counts": {}, "item_to_ag": {}})

    except Exception as e:
        return jsonify({"error": str(e)}),



if __name__ == "__main__":
    app.run(debug=True)
