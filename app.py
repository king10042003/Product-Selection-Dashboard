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
            writer.writerow(["Item Code", "Lot Number", "Unit Weight", "Complexity Code", "Product Group", "Stock Value", "Product Category Description"])
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

            # Read CSV and add IMAGE URL dynamically
            df = pd.read_csv(filepath, dtype=str)
            if "Item Code" in df.columns:
                df["IMAGE"] = df["Item Code"].apply(
                    lambda x: f"https://jewbridge.titanjew.in/CatalogImages/api/ImageFetch/?Type=ProductImages&ImageName={x[2:9]}.jpg"
                )

            # Save processed CSV (overwrite original file with IMAGE column)
            df.to_csv(filepath, index=False)
            
            # Save file path and reset selection in session
            session["uploaded_file"] = filepath
            session["selected_items"] = []  
            session["total_rows"] = len(df)
            return redirect(url_for("dashboard"))
    return render_template("index.html")

# Route: Dashboard (with pagination)
@app.route("/dashboard")
def dashboard():
    file_path = session.get("uploaded_file")
    if not file_path or not os.path.exists(file_path):
        return redirect(url_for("index"))

    # Pagination parameters
    page = int(request.args.get("page", 1))
    per_page = 21

    


    df = pd.read_csv(file_path, dtype=str)

    filter_col = request.args.get("filter_col")
    filter_val = request.args.get("filter_val")  # This will be a comma-separated string
    if filter_col and filter_val:
        filter_col = filter_col.strip()
        filter_values = [val.strip() for val in filter_val.split(",")]
        if filter_col in df.columns:
            df = df[df[filter_col].isin(filter_values)]
        else:
            print(f"Column '{filter_col}' not found in dataframe")
    

    
    # Re-calculate IMAGE URL (in case it is missing)
    if "Item Code" in df.columns:
        df["IMAGE"] = df["Item Code"].apply(
            lambda x: f"https://jewbridge.titanjew.in/CatalogImages/api/ImageFetch/?Type=ProductImages&ImageName={x[2:9]}.jpg"
        )
    total_pages = (len(df) + per_page - 1) // per_page
    paginated_data = df.iloc[(page - 1) * per_page: page * per_page].to_dict(orient="records")

    # Retrieve previously selected items (list of Item Codes)
    selected_items = session.get("selected_items", [])
    column_data = [col for col in df.columns if col not in ["IMAGE", "Sno."]]

    return render_template("dashboard.html", data=paginated_data, total_pages=total_pages, current_page=page, selected_items=selected_items,column_data=column_data)

# Route: Download Sample CSV
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
    selected_items = session.get("selected_items", [])
    file_path = session.get("uploaded_file")
    if not selected_items or not file_path:
        return "No items selected", 400

    df = pd.read_csv(file_path, dtype=str)
    # Ensure IMAGE column is present
    if "Item Code" in df.columns:
        df["IMAGE"] = df["Item Code"].apply(
            lambda x: f"https://jewbridge.titanjew.in/CatalogImages/api/ImageFetch/?Type=ProductImages&ImageName={x[2:9]}.jpg"
        )
    selected_df = df[df["Item Code"].isin(selected_items)]
    selected_df.to_csv(SELECTED_CSV_PATH, index=False)
    return send_file(SELECTED_CSV_PATH, as_attachment=True)

@app.route("/get_unique_values")
def get_unique_values():
    file_path = session.get("uploaded_file")
    column = request.args.get("column")

    if not file_path or not column:
        return jsonify({"values": []})

    df = pd.read_csv(file_path, dtype=str)
    if column in df.columns:
        unique_vals = df[column].dropna().unique().tolist()
        return jsonify({"values": unique_vals})
    else:
        return jsonify({"values": []})

if __name__ == "__main__":
    app.run(debug=True)
