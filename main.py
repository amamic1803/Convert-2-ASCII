import os
import sys
import time
from math import ceil
from multiprocessing import Pool, freeze_support
from threading import Thread
from tkinter import *
from tkinter.filedialog import asksaveasfilename, askopenfilename
from tkinter.messagebox import showerror

import _tkinter
import cv2
import ffmpeg
import numpy as np
from PIL import Image as PIL_Image
from PIL import ImageTk as PIL_ImageTk


def resource_path(relative_path=""):
	""" Get absolute path to resource, works for dev and for PyInstaller """
	try:
		# PyInstaller creates a temp folder and stores path in _MEIPASS
		base_path = sys._MEIPASS
	except Exception:
		base_path = os.path.abspath(".")
	return os.path.join(base_path, relative_path)

def frame_to_ascii(frame, width, height, text_color, font_scale, ascii_scale):
	frame_ascii = np.full((height, width, 3), abs(text_color - 255), dtype="uint8")

	box_size = cv2.getTextSize("$", cv2.FONT_HERSHEY_PLAIN, font_scale, 1)[0][0]
	leftover_height = height % box_size
	for i in range(0, width, box_size):
		cv2.putText(img=frame_ascii, text=ascii_scale[abs(ceil(((int(round(np.average(frame[0: box_size, i:i + box_size]), 0)) + 1) * 35) / 128) - 1 - (69 * (text_color // 255)))], org=(i, leftover_height - 1), fontFace=cv2.FONT_HERSHEY_PLAIN, fontScale=font_scale, color=(text_color, text_color, text_color), thickness=1, lineType=cv2.LINE_AA)
		for j in range(leftover_height, height, box_size):
			cv2.putText(img=frame_ascii, text=ascii_scale[abs(ceil(((int(round(np.average(frame[j:j + box_size, i:i + box_size]), 0)) + 1) * 35) / 128) - 1 - (69 * (text_color // 255)))], org=(i, j + box_size - 1), fontFace=cv2.FONT_HERSHEY_PLAIN, fontScale=font_scale, color=(text_color, text_color, text_color), thickness=1, lineType=cv2.LINE_AA)

	return frame_ascii

def change_thickness(event, widget, typ):
	global started
	if not started:
		if typ:
			widget.config(highlightthickness=1)
		else:
			widget.config(highlightthickness=3)

def convert_change_thickness(event, typ):
	global image_converting
	if not image_converting and not preview_converting:
		if typ:
			convert_btn.config(highlightthickness=1)
		else:
			convert_btn.config(highlightthickness=3)

def browse_click(event):
	global started
	if not started:
		init_dir = os.path.dirname(file_ent.get())
		if not os.path.isdir(init_dir):
			init_dir = os.getcwd()

		selection = askopenfilename(filetypes=(("All files", ""), ("Video files", "*.mp4;*.avi;*.mpg;*.mov;*.wmv;*.mkv"), ("JPEG files", "*.jpeg;*.jpg"), ("Portable Network Graphics", "*.png"), ("Windows bitmaps", "*.bmp;*.dib"), ("WebP", "*.webp"), ("Sun rasters", "*.sr;*.ras"), ("TIFF files", "*.tiff;*.tif")), initialdir=init_dir, parent=root)
		if selection != "":
			file_ent.delete(0, END)
			file_ent.insert(0, selection.replace("/", "\\"))
			file_ent.xview_moveto(1)

def convert_click(event, open_path):
	global selected_text_color, ffprobe_path, started, video_converting, image_converting, video_convert_thread, image_convert_thread, started_no
	if not started:
		started = True
		toggle_ui()
		convert_btn.config(text="Convert", highlightcolor="black", highlightbackground="black", highlightthickness=1)
		preview_btn.config(highlightthickness=1)
		root.update_idletasks()
		if os.path.isfile(open_path):
			og_img = cv2.imread(open_path, cv2.IMREAD_COLOR)
			if og_img is not None:
				save_path = get_save_path(open_path, "img")
				if save_path != "":
					image_converting = True
					start_time = time.time()
					status_line_lbl.config(text="Converting...")
					image_convert_thread = Thread(target=image_converter, args=(og_img, save_path, start_time))
					image_convert_thread.start()
				else:
					started = False
					toggle_ui()
			else:

				longest_video_stream = None
				length_of_longest = 0

				try:
					probe_info = ffmpeg.probe(open_path, cmd=ffprobe_path)
					for i in range(len(probe_info["streams"])):
						try:
							if probe_info["streams"][i]["codec_type"] == "video" and float(probe_info["streams"][i]["bit_rate"]) > 0 and probe_info["streams"][i]["width"] * probe_info["streams"][i]["height"] != 0 and float(probe_info["streams"][i]["duration"]) >= 0.25 and float(probe_info["streams"][i]["duration"]) >= length_of_longest:
								longest_video_stream = i
								length_of_longest = float(probe_info["streams"][i]["duration"])
						except KeyError:
							pass
				except ffmpeg._run.Error:
					pass

				if longest_video_stream is not None:
					save_path = get_save_path(open_path, "video")
					if save_path != "":
						convert_btn.config(text="Stop", highlightcolor="red", highlightbackground="red", highlightthickness=1)
						video_converting = True
						start_time = time.time()
						status_line_lbl.config(text="Converting...")
						root.update_idletasks()
						v_stream_indx = str(longest_video_stream)
						width = probe_info["streams"][longest_video_stream]["width"]
						height = probe_info["streams"][longest_video_stream]["height"]
						fps = eval(probe_info["streams"][longest_video_stream]["avg_frame_rate"])
						pixel_format = probe_info["streams"][longest_video_stream]["pix_fmt"]
						og_codec = probe_info["streams"][longest_video_stream]["codec_name"]
						num_of_frames = int(probe_info["streams"][longest_video_stream]["nb_frames"])

						try:
							fontScale = float(fontscale_ent.get())
						except ValueError:
							fontScale = 0.001
						if fontScale == 0:
							fontScale = 0.001

						video_convert_thread = Thread(target=video_converter, args=(fontScale, selected_text_color, open_path, save_path, v_stream_indx, width, height, fps, pixel_format, og_codec, num_of_frames, start_time, started_no))
						video_convert_thread.start()
					else:
						started = False
						toggle_ui()
				else:
					showerror(title="File Format Error!", message="The specified file's format is not supported!")
					started = False
					toggle_ui()
		else:
			showerror(title="File Not Found!", message="The specified file was not found!")
			started = False
			toggle_ui()
	elif video_converting:
		started = False
		video_converting = False
		started_no += 1
		toggle_ui()
		status_line_lbl.config(text="Stopped")

def preview_click(event, open_path):
	global started, preview_converting, preview_convert_thread, preview_video_convert_thread, ffprobe_path
	if not started:
		started = True
		toggle_ui()
		convert_btn.config(text="Convert", highlightcolor="black", highlightbackground="black", highlightthickness=1)
		preview_btn.config(highlightthickness=1)
		root.update_idletasks()

		if os.path.isfile(open_path):
			og_img = cv2.imread(open_path, cv2.IMREAD_COLOR)
			if og_img is not None:
				preview_converting = True
				status_line_lbl.config(text="Generating...")
				preview_convert_thread = Thread(target=preview_converter, args=(og_img, ))
				preview_convert_thread.start()
			else:

				longest_video_stream = None
				length_of_longest = 0

				try:
					probe_info = ffmpeg.probe(open_path, cmd=ffprobe_path)
					for i in range(len(probe_info["streams"])):
						try:
							if probe_info["streams"][i]["codec_type"] == "video" and float(probe_info["streams"][i]["bit_rate"]) > 0 and probe_info["streams"][i]["width"] * probe_info["streams"][i]["height"] != 0 and float(probe_info["streams"][i]["duration"]) >= 0.25 and float(probe_info["streams"][i]["duration"]) >= length_of_longest:
								longest_video_stream = i
								length_of_longest = float(probe_info["streams"][i]["duration"])
						except KeyError:
							pass
				except ffmpeg._run.Error:
					pass

				if longest_video_stream is not None:
					preview_converting = True
					status_line_lbl.config(text="Generating...")
					v_stream_indx = str(longest_video_stream)
					width = probe_info["streams"][longest_video_stream]["width"]
					height = probe_info["streams"][longest_video_stream]["height"]

					try:
						fontScale = float(fontscale_ent.get())
					except ValueError:
						fontScale = 0.001
					if fontScale == 0:
						fontScale = 0.001

					preview_video_convert_thread = Thread(target=preview_video_converter, args=(fontScale, selected_text_color, open_path, v_stream_indx, width, height))
					preview_video_convert_thread.start()
				else:
					showerror(title="File Format Error!", message="The specified file's format is not supported!")
					started = False
					toggle_ui()
		else:
			showerror(title="File Not Found!", message="The specified file was not found!")
			started = False
			toggle_ui()

def get_save_path(og_path, data_type):
	init_name, init_extension = os.path.splitext(os.path.basename(og_path))
	init_dir = os.path.dirname(og_path)
	if data_type == "img":
		init_filetypes = (("Image file", f"*{init_extension}"), )
	else:
		init_filetypes = (("Video file", f"*{init_extension}"), )
	return asksaveasfilename(confirmoverwrite=True, defaultextension=init_extension, filetypes=init_filetypes, initialdir=init_dir, parent=root, initialfile=f"""{init_name}-ASCII-{str(time.time()).replace(".", "")}""")  # {time.strftime("%Y-%m-%d--%H-%M-%S")}

def change_color_select_thickness(event, widget, color, typ):
	global selected_text_color, started
	if color == selected_text_color and not started:
		if typ:
			widget.config(highlightcolor="red", highlightbackground="red")
		else:
			widget.config(highlightcolor="green", highlightbackground="green")

def color_select_click(event, color):
	global selected_text_color, started
	if color == selected_text_color and not started:
		if color == 0:
			background_white.config(highlightthickness=7, highlightcolor="red", highlightbackground="red")
			background_black.config(highlightthickness=4, highlightcolor="green", highlightbackground="green")
		else:
			background_white.config(highlightthickness=4, highlightcolor="green", highlightbackground="green")
			background_black.config(highlightthickness=7, highlightcolor="red", highlightbackground="red")
		selected_text_color = abs(selected_text_color - 255)

def validate_input(full_text):
	if " " in full_text or "-" in full_text or full_text.count(".") > 1 or len(full_text) > 5:
		return False
	elif full_text == "" or full_text == ".":
		return True
	else:
		try:
			float(full_text)
			return True
		except ValueError:
			return False

def change_to_ready(full_text):
	status_line_lbl.config(text="Ready")
	return True

def video_converter(font_scale, color, open_path, save_path, v_stream_indx, width, height, fps, pixel_format, og_codec, num_of_frames, start_time, start_time_no):
	global ffmpeg_path, ascii_scale, started, video_converting, started_no

	process_in = (ffmpeg
	              .input(open_path, r=fps)[v_stream_indx]
	              .output('pipe:', format='rawvideo', pix_fmt='rgb24', r=fps)
	              .global_args("-loglevel", "quiet")
	              .run_async(pipe_stdout=True, cmd=ffmpeg_path)
	              )
	process_out = (ffmpeg
	               .input('pipe:', format='rawvideo', pix_fmt='rgb24', s=f'{width}x{height}', r=fps)
	               .output(ffmpeg.input(open_path, r=fps, vn=None), save_path, pix_fmt=pixel_format, r=fps, vcodec=og_codec, codec="copy")
	               .global_args("-loglevel", "quiet")
	               .overwrite_output()
	               .run_async(pipe_stdin=True, cmd=ffmpeg_path)
	               )
	num_of_cpus = os.cpu_count()
	status_line_lbl.config(text=f"Converting... 0.0 %")
	broken = False
	with Pool(processes=num_of_cpus) as pool:
		queue_list = []
		ended = False
		count_frames = 0
		while True:
			if start_time_no != started_no:
				broken = True
				break
			elif len(queue_list) < 2 * num_of_cpus and not ended:
				in_bytes = process_in.stdout.read(width * height * 3)
				if not in_bytes:
					break
				else:
					in_frame = np.frombuffer(in_bytes, np.uint8).reshape([height, width, 3])
					queue_list.append(pool.apply_async(frame_to_ascii, args=(in_frame, width, height, color, font_scale, ascii_scale)))
					count_frames += 1
					if count_frames < num_of_frames and start_time_no == started_no:
						status_line_lbl.config(text=f"Converting... {round((count_frames / num_of_frames) * 100, 1)} %")
			elif ended and len(queue_list) == 0:
				break
			else:
				out_frame = queue_list[0].get()
				process_out.stdin.write(out_frame.astype(np.uint8).tobytes())
				queue_list.pop(0)
				if count_frames == num_of_frames and start_time_no == started_no:
					lower_percentage = ((count_frames - 1) / num_of_frames) * 100
					status_line_lbl.config(text=f"Converting... {round(lower_percentage + ((100 - lower_percentage) * abs(len(queue_list) - (num_of_cpus * 2))), 1)} %")

	process_out.stdin.close()
	process_in.stdout.close()
	process_out.wait()
	process_in.wait()
	if broken:
		try:
			os.remove(save_path)
		except OSError:
			pass
	else:
		started = False
		video_converting = False
		toggle_ui()
		status_line_lbl.config(text=f"Completed ({round(time.time() - start_time, 3)} s)")

def image_converter(og_img, save_path, start_time):
	global started, image_converting, selected_text_color, ascii_scale
	height, width, depth = og_img.shape
	try:
		fontScale = float(fontscale_ent.get())
	except ValueError:
		fontScale = 0.001
	if fontScale == 0:
		fontScale = 0.001
	converted_img = cv2.cvtColor(frame_to_ascii(og_img, width, height, selected_text_color, fontScale, ascii_scale), cv2.COLOR_BGR2GRAY)
	cv2.imwrite(save_path, converted_img)
	if not started:
		try:
			os.remove(save_path)
		except OSError:
			pass
	started = False
	image_converting = False
	try:
		status_line_lbl.config(text=f"Completed ({round(time.time() - start_time, 3)} s)")
		toggle_ui()
	except RuntimeError:
		pass

def preview_converter(og_img):
	global started, preview_converting, selected_text_color, ascii_scale
	try:
		height, width, depth = og_img.shape
		try:
			fontScale = float(fontscale_ent.get())
		except ValueError:
			fontScale = 0.001
		if fontScale == 0:
			fontScale = 0.001
		preview_img = frame_to_ascii(og_img, width, height, selected_text_color, fontScale, ascii_scale)
		width_fx = (root.winfo_screenwidth() * 0.8) / width
		height_fx = (root.winfo_screenheight() * 0.8) / height
		shrink_f = min(width_fx, height_fx)
		if shrink_f < 1:
			preview_img = cv2.resize(preview_img, (0, 0), fx=shrink_f, fy=shrink_f, interpolation=cv2.INTER_AREA)
		preview_img = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)

		height, width, depth = preview_img.shape

		started = False
		preview_converting = False

		status_line_lbl.config(text=f"Preview")
		root.update_idletasks()

		preview_window = Toplevel(root)
		preview_window.title("Preview")
		preview_window.geometry(f"{width}x{height}+{(root.winfo_screenwidth() // 2) - (width // 2)}+{(root.winfo_screenheight() // 2) - (height // 2)}")
		preview_image_object = PIL_Image.fromarray(preview_img)
		preview_image_object = PIL_ImageTk.PhotoImage(image=preview_image_object)
		preview_widget = Label(preview_window, image=preview_image_object)
		preview_widget.place(x=0, y=0, width=width, height=height)
		preview_window.iconbitmap(resource_path("data/convert-icon.ico"))
		preview_window.grab_set()
		preview_window.resizable(False, False)
		preview_window.wait_window()
		status_line_lbl.config(text=f"Ready")
		toggle_ui()
	except (RuntimeError, _tkinter.TclError):
		pass

def preview_video_converter(font_scale, color, open_path, v_stream_indx, width, height):
	global ffmpeg_path, ascii_scale, started, preview_converting

	try:
		out_img, err = (ffmpeg
		               .input(open_path, ss=0)[v_stream_indx]
		               .output('pipe:', vframes=1, format='image2', vcodec="mjpeg")
		               .run(capture_stdout=True, cmd=ffmpeg_path)
		               )

		preview_og_image = cv2.imdecode(np.asarray(bytearray(out_img), dtype="uint8"), cv2.IMREAD_COLOR)

		preview_img = frame_to_ascii(preview_og_image, width, height, color, font_scale, ascii_scale)
		width_fx = (root.winfo_screenwidth() * 0.8) / width
		height_fx = (root.winfo_screenheight() * 0.8) / height
		shrink_f = min(width_fx, height_fx)
		if shrink_f < 1:
			preview_img = cv2.resize(preview_img, (0, 0), fx=shrink_f, fy=shrink_f, interpolation=cv2.INTER_AREA)
		preview_img = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)

		height, width, depth = preview_img.shape

		started = False
		preview_converting = False

		status_line_lbl.config(text=f"Preview")
		root.update_idletasks()

		preview_window = Toplevel(root)
		preview_window.title("Preview")
		preview_window.geometry(f"{width}x{height}+{(root.winfo_screenwidth() // 2) - (width // 2)}+{(root.winfo_screenheight() // 2) - (height // 2)}")
		preview_image_object = PIL_Image.fromarray(preview_img)
		preview_image_object = PIL_ImageTk.PhotoImage(image=preview_image_object)
		preview_widget = Label(preview_window, image=preview_image_object)
		preview_widget.place(x=0, y=0, width=width, height=height)
		preview_window.iconbitmap(resource_path("data/convert-icon.ico"))
		preview_window.grab_set()
		preview_window.resizable(False, False)
		preview_window.wait_window()
		status_line_lbl.config(text=f"Ready")
		toggle_ui()
	except (RuntimeError, _tkinter.TclError):
		pass

def toggle_ui():
	global started, selected_text_color

	if started:
		file_ent.config(state=DISABLED, highlightcolor="black", highlightbackground="black")
		browse_btn.config(highlightcolor="black", highlightbackground="black")
		background_black.config(highlightcolor="grey25", highlightbackground="grey25")
		background_white.config(highlightcolor="grey25", highlightbackground="grey25")
		fontscale_ent.config(state=DISABLED, highlightcolor="black", highlightbackground="black")
		preview_btn.config(highlightcolor="black", highlightbackground="black")
		convert_btn.config(text="Stop", highlightcolor="red", highlightbackground="red")
	else:
		file_ent.config(state=NORMAL, highlightcolor="green", highlightbackground="green")
		browse_btn.config(highlightcolor="green", highlightbackground="green")
		fontscale_ent.config(state=NORMAL, highlightcolor="green", highlightbackground="green")
		preview_btn.config(highlightcolor="green", highlightbackground="green")
		convert_btn.config(text="Convert", highlightcolor="green", highlightbackground="green")

		if selected_text_color:
			background_black.config(highlightcolor="green", highlightbackground="green")
			background_white.config(highlightcolor="red", highlightbackground="red")
		else:
			background_black.config(highlightcolor="red", highlightbackground="red")
			background_white.config(highlightcolor="green", highlightbackground="green")

def main():
	global started
	global ascii_scale
	global ffmpeg_path, ffprobe_path
	global selected_text_color, started_no

	global image_converting, video_converting
	global image_convert_thread, video_convert_thread
	global preview_converting, preview_convert_thread, preview_video_convert_thread

	global root
	global convert_btn, preview_btn, browse_btn
	global file_ent, fontscale_ent
	global status_line_lbl
	global background_white, background_black

	ascii_scale = r"""$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,"^`'. """
	ffmpeg_path = resource_path("run-data/ffmpeg/bin/ffmpeg.exe")
	ffprobe_path = resource_path("run-data/ffmpeg/bin/ffprobe.exe")

	selected_text_color = 0
	started_no = 1
	started = False
	video_converting = False
	image_converting = False
	preview_converting = False
	video_convert_thread = None
	image_convert_thread = None
	preview_convert_thread = None
	preview_video_convert_thread = None

	root = Tk()
	root.title("Convert-2-ASCII")
	root.resizable(False, False)
	root.iconbitmap(resource_path("data/convert-icon.ico"))
	root.config(background="#202A44")
	root.geometry(f"500x250+{root.winfo_screenwidth() // 2 - 250}+{root.winfo_screenheight() // 2 - 125}")

	reg = root.register(validate_input)
	reg_ready = root.register(change_to_ready)

	title = Label(root, text="Convert-2-ASCII", font=("Helvetica", 30, "bold", "italic"), borderwidth=0, background="#202A44", activebackground="#202A44", foreground="#ffffff", activeforeground="#ffffff")
	title.place(x=0, y=0, width=500, height=100)

	file_lbl = Label(root, text="File:", font=("Helvetica", 12, "bold"), borderwidth=0, background="#202A44", activebackground="#202A44", foreground="#ffffff", activeforeground="#ffffff")
	file_lbl.place(x=0, y=150, width=50, height=30)
	file_ent = Entry(root, font=("Helvetica", 10), validate="key", validatecommand=(reg_ready, "%P"), borderwidth=0, highlightthickness=1, highlightbackground="green", highlightcolor="green", disabledbackground="grey15", disabledforeground="#ffffff", background="grey15", foreground="#ffffff", justify=LEFT, insertbackground="#ffffff")
	file_ent.place(x=46, y=150, width=390, height=30)
	browse_btn = Label(root, text="Browse", font=("Helvetica", 10), highlightthickness=1, highlightbackground="green", highlightcolor="green", borderwidth=0, background="grey15", activebackground="grey15", foreground="#ffffff", activeforeground="#ffffff")
	browse_btn.place(x=435, y=150, width=65, height=30)
	browse_btn.bind("<Enter>", lambda event: change_thickness(event, browse_btn, False))
	browse_btn.bind("<Leave>", lambda event: change_thickness(event, browse_btn, True))
	browse_btn.bind("<ButtonRelease-1>", browse_click)

	background_lbl = Label(root, text="Background:", font=("Helvetica", 12, "bold"), borderwidth=0, background="#202A44", activebackground="#202A44", foreground="#ffffff", activeforeground="#ffffff")
	background_lbl.place(x=270, y=105, width=100, height=30)
	background_white = Label(root, highlightthickness=4, highlightbackground="green", highlightcolor="green", borderwidth=0, background="#ffffff", activebackground="#ffffff")
	background_white.place(x=375, y=105, width=30, height=30)
	background_white.bind("<Enter>", lambda event: change_color_select_thickness(event, background_white, 255, False))
	background_white.bind("<Leave>", lambda event: change_color_select_thickness(event, background_white, 255, True))
	background_white.bind("<ButtonRelease-1>", lambda event: color_select_click(event, 255))
	background_black = Label(root, highlightthickness=7, highlightbackground="red", highlightcolor="red", borderwidth=0, background="#000000", activebackground="#000000")
	background_black.place(x=405, y=105, width=30, height=30)
	background_black.bind("<Enter>", lambda event: change_color_select_thickness(event, background_black, 0, False))
	background_black.bind("<Leave>", lambda event: change_color_select_thickness(event, background_black, 0, True))
	background_black.bind("<ButtonRelease-1>", lambda event: color_select_click(event, 0))

	fontscale_lbl = Label(root, text="Font scale:", font=("Helvetica", 12, "bold"), borderwidth=0, background="#202A44", activebackground="#202A44", foreground="#ffffff", activeforeground="#ffffff")
	fontscale_lbl.place(x=50, y=105, width=85, height=30)
	fontscale_ent = Entry(root, font=("Helvetica", 10), validate="key", validatecommand=(reg, "%P"), justify=CENTER, borderwidth=0, highlightthickness=1, highlightbackground="green", highlightcolor="green", disabledbackground="grey15", disabledforeground="#ffffff", background="grey15", foreground="#ffffff", insertbackground="#ffffff")
	fontscale_ent.place(x=140, y=105, width=50, height=30)
	fontscale_ent.insert(0, "0.5")

	convert_btn = Label(root, text="Convert", font=("Helvetica", 10), highlightthickness=1, highlightbackground="green", highlightcolor="green", borderwidth=0, background="grey15", activebackground="grey15", foreground="#ffffff", activeforeground="#ffffff")
	convert_btn.place(x=370, y=203, width=100, height=30)
	convert_btn.bind("<Enter>", lambda event: convert_change_thickness(event, False))
	convert_btn.bind("<Leave>", lambda event: convert_change_thickness(event, True))
	convert_btn.bind("<ButtonRelease-1>", lambda event: convert_click(event, file_ent.get()))

	preview_btn = Label(root, text="Preview", font=("Helvetica", 10), highlightthickness=1, highlightbackground="green", highlightcolor="green", borderwidth=0, background="grey15", activebackground="grey15", foreground="#ffffff", activeforeground="#ffffff")
	preview_btn.place(x=30, y=203, width=100, height=30)
	preview_btn.bind("<Enter>", lambda event: change_thickness(event, preview_btn, False))
	preview_btn.bind("<Leave>", lambda event: change_thickness(event, preview_btn, True))
	preview_btn.bind("<ButtonRelease-1>", lambda event: preview_click(event, file_ent.get()))

	status_line_lbl = Label(root, text="Ready", font=("Helvetica", 9, "bold"), borderwidth=0, background="#202A44", activebackground="#202A44", foreground="#ffffff", activeforeground="#ffffff")
	status_line_lbl.place(x=130, y=203, width=240, height=30)

	root.mainloop()

	try:
		root.destroy()
	except _tkinter.TclError:
		pass
	started = False
	try:
		video_convert_thread.join()
	except AttributeError:
		pass
	try:
		image_convert_thread.join()
	except AttributeError:
		pass
	try:
		preview_convert_thread.join()
	except AttributeError:
		pass
	try:
		preview_video_convert_thread.join()
	except AttributeError:
		pass


if __name__ == "__main__":
	freeze_support()

	main()
