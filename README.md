# RatYourself
**THIS SOFTWARE IS CREATED WITH AI, DO NOT TAKE THIS SERIOUSLY** 

Program that lets you see your own screen with jank in a browser.

basically what this does is it allows you to see your own screen in a browser window (your-ip:5555) and kind of control it but its really janky and I made it in like 5 seconds with ai.

This thing has no real purpose other than for the funnies.

To build the exe run: `python -m PyInstaller --onefile --noconsole --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 --hidden-import=PIL.Image --hidden-import=mss --hidden-import=pyautogui rat_panel_v2.py` in the file directory.

Dependencies: `pip install flask pyautogui pillow mss pynput requests`, `pip install pyinstaller`

This only works on windows and you must have python 3 installed.. obviously
