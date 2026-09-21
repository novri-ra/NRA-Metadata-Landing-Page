import os
import sys
import urllib.request
import zipfile
import tarfile
import shutil

def main():
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools')
    os.makedirs(tools_dir, exist_ok=True)
    
    exiftool_exe = os.path.join(tools_dir, 'exiftool', 'exiftool.exe')
    ffmpeg_exe = os.path.join(tools_dir, 'ffmpeg', 'bin', 'ffmpeg.exe')

    try:
        # 1. Setup ExifTool
        if not os.path.exists(exiftool_exe):
            print("Downloading ExifTool...")
            url = "https://github.com/exiftool/exiftool/archive/refs/heads/master.zip"
            zip_path = os.path.join(tools_dir, "exiftool_temp.zip")
            urllib.request.urlretrieve(url, zip_path)
            
            print("Extracting ExifTool...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tools_dir)
            
            extracted_dir = None
            for item in os.listdir(tools_dir):
                if item.startswith('exiftool-') and os.path.isdir(os.path.join(tools_dir, item)):
                    extracted_dir = os.path.join(tools_dir, item)
                    break
            
            if extracted_dir:
                exiftool_dir = os.path.join(tools_dir, 'exiftool')
                if os.path.exists(exiftool_dir):
                    shutil.rmtree(exiftool_dir)
                
                exiftool_k = os.path.join(extracted_dir, 'exiftool(-k).exe')
                if os.path.exists(exiftool_k):
                    os.rename(exiftool_k, os.path.join(extracted_dir, 'exiftool.exe'))
                    
                os.rename(extracted_dir, exiftool_dir)
                
            if os.path.exists(zip_path):
                os.remove(zip_path)
        else:
            print("ExifTool sudah terpasang.")

        # 2. Setup FFmpeg
        if not os.path.exists(ffmpeg_exe):
            print("Downloading FFmpeg...")
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            zip_path = os.path.join(tools_dir, "ffmpeg_temp.zip")
            urllib.request.urlretrieve(url, zip_path)
            
            print("Extracting FFmpeg...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tools_dir)
            
            extracted_dir = None
            for item in os.listdir(tools_dir):
                if item.startswith('ffmpeg-') and os.path.isdir(os.path.join(tools_dir, item)):
                    extracted_dir = os.path.join(tools_dir, item)
                    break
                    
            if extracted_dir:
                ffmpeg_dir = os.path.join(tools_dir, 'ffmpeg')
                if os.path.exists(ffmpeg_dir):
                    shutil.rmtree(ffmpeg_dir)
                os.rename(extracted_dir, ffmpeg_dir)
                
            if os.path.exists(zip_path):
                os.remove(zip_path)
        else:
            print("FFmpeg sudah terpasang.")

    except Exception as e:
        print(f"Exception occurred: {e}")
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()