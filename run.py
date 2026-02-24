import subprocess
import os
import sys

def main():
    # Paths
    output_dir = "output"
    png_dir = "pngs"

    # Ensure png output directory exists
    os.makedirs(png_dir, exist_ok=True)

    # Run generate.py
    print("Running generate.py...")
    result = subprocess.run([sys.executable, "src/main.py"])

    # Stop if generate.py failed
    if result.returncode != 0:
        print("generate.py failed. Aborting.")
        sys.exit(1)

    print("generate.py completed.")

    # Process .dot files
    for filename in os.listdir(output_dir):
        if filename.lower().endswith(".dot"):
            dot_path = os.path.join(output_dir, filename)

            name_without_ext = os.path.splitext(filename)[0]
            png_path = os.path.join(png_dir, f"{name_without_ext}.png")

            cmd = [
                "dot",
                "-Tpng:cairo",
                "-Gdpi=300",
                dot_path,
                "-o",
                png_path
            ]

            print(f"Converting {filename} -> {png_path}")

            result = subprocess.run(cmd)

            if result.returncode != 0:
                print(f"Failed to convert {filename}")

    print("All files processed.")


if __name__ == "__main__":
    main()