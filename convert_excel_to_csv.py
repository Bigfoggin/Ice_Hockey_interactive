from pathlib import Path
import pandas as pd


def convert_all_excel_to_csv(root_dir="data"):
  root_path = Path(root_dir)

  if not root_path.exists():
    print(f"Directory '{root_dir}' does not exist.")
    return

  # .rglob('*.xlsx') digs as deep as possible into subdirectories
  excel_files = list(root_path.rglob("*.xlsx"))

  if not excel_files:
    print(f"No .xlsx files found inside '{root_dir}' or its subfolders.")
    return

  print(f"Found {len(excel_files)} Excel file(s). Starting conversion...\n")

  for file_path in excel_files:
    try:
      # sheet_name=None tells pandas to load ALL sheets into a dictionary:
      # Keys = sheet names, Values = DataFrames
      excel_data = pd.read_excel(file_path, sheet_name=None)

      for sheet_name, df in excel_data.items():
        # Clean sheet name to avoid invalid characters in filenames
        safe_sheet_name = "".join(
            c if c.isalnum() or c in ("_", "-") else "_" for c in sheet_name
        )

        # Create a descriptive CSV filename in the same directory as the excel file
        # Format: original_name_sheetname.csv
        csv_filename = (
            file_path.parent / f"{file_path.stem}_{safe_sheet_name}.csv"
        )

        # Export to CSV
        df.to_csv(csv_filename, index=False)
        print(f"✔ Converted: {file_path.relative_to(root_path)}")
        print(f"   └── Sheet '{sheet_name}' -> {csv_filename.name}")

    except Exception as e:
      print(f"❌ Error processing {file_path}: {e}")

  print("\nConversion complete!")


if __name__ == "__main__":
  convert_all_excel_to_csv("data")