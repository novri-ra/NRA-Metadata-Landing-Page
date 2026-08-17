import os
import sys
import subprocess
import xml.etree.ElementTree as ET

class MediaProcessor:
    def get_base_path(self) -> str:
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

    def get_tool_path(self, tool_name: str) -> str:
        base = self.get_base_path()
        if sys.platform == "win32":
            if tool_name == "exiftool": return os.path.join(base, "tools", "exiftool", "exiftool.exe")
            if tool_name == "ghostscript": return os.path.join(base, "tools", "ghostscript", "bin", "gswin64c.exe")
            if tool_name == "ffmpeg": return os.path.join(base, "tools", "ffmpeg", "ffmpeg.exe")
        return tool_name

    def embed_metadata(self, file_path: str, title: str, description: str, keywords: list[str], copyright_text: str) -> bool:
        ext = file_path.lower().split('.')[-1]
        if ext == 'svg':
            return self._embed_svg_metadata(file_path, title, description, keywords, copyright_text)

        exiftool_path = self.get_tool_path("exiftool")
        cmd = [exiftool_path, "-overwrite_original", f"-Title={title}", f"-ObjectName={title}", f"-Description={description}", f"-Caption-Abstract={description}", f"-ImageDescription={description}", f"-Copyright={copyright_text}", f"-Rights={copyright_text}"]
        for kw in keywords:
            cmd.extend([f"-Keywords={kw}", f"-Subject={kw}"])
        cmd.append(file_path)

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"ExifTool error: {e.stderr}")
            return False

    def _embed_svg_metadata(self, file_path: str, title: str, description: str, keywords: list[str], copyright_text: str) -> bool:
        try:
            ET.register_namespace('', "http://www.w3.org/2000/svg")
            ET.register_namespace('dc', "http://purl.org/dc/elements/1.1/")
            tree = ET.parse(file_path)
            root = tree.getroot()
            title_el = ET.Element('{http://www.w3.org/2000/svg}title')
            title_el.text = title
            desc_el = ET.Element('{http://www.w3.org/2000/svg}desc')
            desc_el.text = description
            root.insert(0, desc_el)
            root.insert(0, title_el)
            tree.write(file_path, encoding='utf-8', xml_declaration=True)
            return True
        except Exception as e:
            print(f"SVG metadata error: {e}")
            return False
