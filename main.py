import collections
import multiprocessing
import os
import random
import statistics
import sys
import threading
import time
import tkinter as tk
from tkinter.colorchooser import askcolor
from tkinter.filedialog import asksaveasfilename, askopenfilename
from tkinter.messagebox import showerror

import cv2
import ffmpeg
import numpy as np
from PIL import Image as PIL_Image
from PIL import ImageTk as PIL_ImageTk


ASCII_SCALE = r"""$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,"^`'. """

def frame_to_ascii(frame, font_scale, front_color, back_color):
	front_color = hex_to_rgb(front_color)
	back_color = hex_to_rgb(back_color)

	front_brightness = statistics.mean(front_color)
	back_brightness = statistics.mean(back_color)

	height, width, _ = frame.shape
	pixel = np.array(back_color, dtype="uint8")
	frame_ascii = np.full((height, width, 3), pixel, dtype="uint8")

	if back_brightness > front_brightness:
		def ascii_char(x_l, x_h, y_l, y_h) -> str:
			return ASCII_SCALE[int(round(np.average(frame[y_l:y_h, x_l:x_h]) / 255 * (len(ASCII_SCALE) - 1), 0))]
	else:
		def ascii_char(x_l, x_h, y_l, y_h) -> str:
			return ASCII_SCALE[len(ASCII_SCALE) - 1 - int(round(np.average(frame[y_l:y_h, x_l:x_h]) / 255 * (len(ASCII_SCALE) - 1), 0))]

	box_size = cv2.getTextSize("$", cv2.FONT_HERSHEY_PLAIN, font_scale, 1)[0][0]
	leftover_height = height % box_size
	for i in range(0, width, box_size):
		if leftover_height != 0:
			cv2.putText(
				img=frame_ascii,
				text=ascii_char(i, i + box_size, 0, leftover_height),
				org=(i, leftover_height - 1),
				fontFace=cv2.FONT_HERSHEY_PLAIN,
				fontScale=font_scale,
				color=front_color,
				thickness=1,
				lineType=cv2.LINE_AA
			)
		for j in range(leftover_height, height, box_size):
			cv2.putText(
				img=frame_ascii,
				text=ascii_char(i, i + box_size, j, j + box_size),
				org=(i, j + box_size - 1),
				fontFace=cv2.FONT_HERSHEY_PLAIN,
				fontScale=font_scale,
				color=front_color,
				thickness=1,
				lineType=cv2.LINE_AA
			)

	return frame_ascii

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
	hex_color = hex_color.lstrip("#")
	return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

class App:
	def __init__(self):
		self.ffmpeg_path = self.resource_path("resources/ffmpeg/bin/ffmpeg.exe")
		self.ffprobe_path = self.resource_path("resources/ffmpeg/bin/ffprobe.exe")

		self.front_color = "#000000"
		self.back_color = "#ffffff"

		self.job_id = 1
		self.processing = False
		self.processing_video = False

		self.img_cvt_thread = None
		self.vid_cvt_thread = None
		self.preview_img_cvt_thread = None
		self.preview_vid_cvt_thread = None

		self.root = tk.Tk()
		self.root.title("Convert-2-ASCII")
		self.root.resizable(False, False)
		self.root.iconbitmap(self.resource_path("resources/convert-icon.ico"))
		self.root.config(background="#202A44")
		self.root.geometry(f"500x250+{self.root.winfo_screenwidth() // 2 - 250}+{self.root.winfo_screenheight() // 2 - 125}")
		self.root.protocol("WM_DELETE_WINDOW", self.close_app)

		self.title = tk.Label(self.root, text="Convert-2-ASCII", font=("Helvetica", 30, "bold", "italic"),
		                      borderwidth=0, background="#202A44", activebackground="#202A44",
		                      foreground="#ffffff", activeforeground="#ffffff")
		self.title.place(x=0, y=0, width=500, height=100)

		self.status_line_lbl = tk.Label(self.root, text="Ready", font=("Helvetica", 9, "bold"), borderwidth=0,
		                                background="#202A44", activebackground="#202A44",
		                                foreground="#ffffff", activeforeground="#ffffff")
		self.status_line_lbl.place(x=130, y=203, width=240, height=30)

		self.file_lbl = tk.Label(self.root, text="File:", font=("Helvetica", 12, "bold"), borderwidth=0,
		                         background="#202A44", activebackground="#202A44",
		                         foreground="#ffffff", activeforeground="#ffffff")
		self.file_lbl.place(x=0, y=150, width=50, height=30)

		self.reg_ready = self.root.register(lambda: self.status_line_lbl.config(text="Ready") or True)  # change status line to "Ready" when entry is edited
		self.file_ent = tk.Entry(self.root, font=("Helvetica", 10), validate="key", validatecommand=self.reg_ready,
		                         borderwidth=0, highlightthickness=1, highlightbackground="green", highlightcolor="green",
		                         disabledbackground="grey15", disabledforeground="#ffffff", background="grey15",
		                         foreground="#ffffff", justify=tk.LEFT, insertbackground="#ffffff")
		self.file_ent.place(x=46, y=150, width=385, height=30)

		self.browse_btn = tk.Label(self.root, text="Browse", font=("Helvetica", 10), cursor="hand2",
		                           highlightthickness=1, borderwidth=0, highlightbackground="green", highlightcolor="green",
		                           background="grey15", activebackground="grey15",
		                           foreground="#ffffff", activeforeground="#ffffff")
		self.browse_btn.place(x=430, y=150, width=65, height=30)
		self.browse_btn.bind("<Enter>", lambda event: self.browse_btn.config(highlightthickness=3) if not self.processing else None)
		self.browse_btn.bind("<Leave>", lambda event: self.browse_btn.config(highlightthickness=1) if not self.processing else None)
		self.browse_btn.bind("<ButtonRelease-1>", lambda event: self.browse_click())

		self.colors_lbl = tk.Label(self.root, text="Colors:", font=("Helvetica", 12, "bold"), borderwidth=0,
		                           background="#202A44", activebackground="#202A44",
		                           foreground="#ffffff", activeforeground="#ffffff")
		self.colors_lbl.place(x=290, y=105, width=100, height=30)

		self.color_front_lbl = tk.Label(self.root, cursor="hand2", borderwidth=0, background=self.front_color, activebackground=self.front_color,
		                                highlightthickness=2, highlightbackground="green", highlightcolor="green")
		self.color_front_lbl.place(x=375, y=105, width=30, height=30)
		self.color_front_lbl.bind("<ButtonRelease-1>", lambda event: self.choose_color("front"))

		self.color_back_lbl = tk.Label(self.root, cursor="hand2", borderwidth=0, background=self.back_color, activebackground=self.back_color,
		                               highlightthickness=2, highlightbackground="green", highlightcolor="green")
		self.color_back_lbl.place(x=410, y=105, width=30, height=30)
		self.color_back_lbl.bind("<ButtonRelease-1>", lambda event: self.choose_color("back"))

		self.fontscale_lbl = tk.Label(self.root, text="Font scale:", font=("Helvetica", 12, "bold"), borderwidth=0,
		                              background="#202A44", activebackground="#202A44",
		                              foreground="#ffffff", activeforeground="#ffffff")
		self.fontscale_lbl.place(x=50, y=105, width=85, height=30)
		self.fontscale_ent_reg = self.root.register(self.validate_fontscale)
		self.fontscale_ent = tk.Entry(self.root, font=("Helvetica", 10), justify=tk.CENTER, borderwidth=0,
		                              validate="key", validatecommand=(self.fontscale_ent_reg, "%P"),
		                              highlightthickness=1, highlightbackground="green", highlightcolor="green",
		                              disabledbackground="grey15", disabledforeground="#ffffff",
		                              background="grey15", foreground="#ffffff", insertbackground="#ffffff")
		self.fontscale_ent.place(x=140, y=105, width=50, height=30)
		self.fontscale_ent.insert(0, "0.5")

		self.convert_btn = tk.Label(self.root, text="Convert", font=("Helvetica", 10), borderwidth=0, cursor="hand2",
		                            highlightthickness=1, highlightbackground="green", highlightcolor="green",
		                            background="grey15", activebackground="grey15",
		                            foreground="#ffffff", activeforeground="#ffffff")
		self.convert_btn.place(x=370, y=203, width=100, height=30)
		self.convert_btn.bind("<Enter>", lambda event: self.convert_btn.config(highlightthickness=3) if not self.processing or self.processing_video else None)
		self.convert_btn.bind("<Leave>", lambda event: self.convert_btn.config(highlightthickness=1) if not self.processing or self.processing_video else None)
		self.convert_btn.bind("<ButtonRelease-1>", lambda event: self.convert_click())

		self.preview_btn = tk.Label(self.root, text="Preview", font=("Helvetica", 10), borderwidth=0, cursor="hand2",
		                            highlightthickness=1, highlightbackground="green", highlightcolor="green",
		                            background="grey15", activebackground="grey15",
		                            foreground="#ffffff", activeforeground="#ffffff")
		self.preview_btn.place(x=30, y=203, width=100, height=30)
		self.preview_btn.bind("<Enter>", lambda event: self.preview_btn.config(highlightthickness=3) if not self.processing else None)
		self.preview_btn.bind("<Leave>", lambda event: self.preview_btn.config(highlightthickness=1) if not self.processing else None)
		self.preview_btn.bind("<ButtonRelease-1>", lambda event: self.preview_click())

		self.root.mainloop()

	def close_app(self):
		if self.processing_video:
			showerror(title="Processing Video", message="Please stop the video conversion before closing the app!", parent=self.root)
		else:
			self.root.destroy()

	def choose_color(self, place: str):
		if not self.processing:
			match place:
				case "front":
					new_color = askcolor(initialcolor=self.front_color, parent=self.root, title="Choose foreground color")
					if new_color[1] is not None:
						self.front_color = new_color[1]
						self.color_front_lbl.config(background=self.front_color, activebackground=self.front_color)
						self.status_line_lbl.config(text="Ready")
				case "back":
					new_color = askcolor(initialcolor=self.back_color, parent=self.root, title="Choose background color")
					if new_color[1] is not None:
						self.back_color = new_color[1]
						self.color_back_lbl.config(background=self.back_color, activebackground=self.back_color)
						self.status_line_lbl.config(text="Ready")
				case _:
					raise ValueError("place must be either 'front' or 'back'")

	def get_save_path(self, og_path, video=False):
		init_name, init_extension = os.path.splitext(os.path.basename(og_path))

		if not video:
			init_extension = ".png"  # always use PNG for images

		init_dir = os.path.dirname(og_path)
		if not video:
			init_filetypes = (("Image file", f"*{init_extension}"),)
		else:
			init_filetypes = (("Video file", f"*{init_extension}"),)

		return asksaveasfilename(
			confirmoverwrite=True,
			defaultextension=init_extension,
			filetypes=init_filetypes,
			initialdir=init_dir,
			parent=self.root,
			initialfile=f"""{init_name}-ASCII-{str(time.time()).replace(".", "")}""")

	def browse_click(self):
		if not self.processing:
			init_dir = os.path.dirname(self.file_ent.get())
			if not os.path.isdir(init_dir):
				init_dir = os.path.dirname(sys.executable)
			if not os.path.isdir(init_dir):
				init_dir = os.path.join(os.path.expanduser('~'), 'Desktop')

			selection = askopenfilename(filetypes=(
				("All files", ""),
				("Video files", "*.mp4;*.avi;*.mpg;*.mov;*.wmv;*.mkv"),
				("JPEG files", "*.jpeg;*.jpg"),
				("Portable Network Graphics", "*.png"),
				("Windows bitmaps", "*.bmp;*.dib"),
				("WebP", "*.webp"),
				("Sun rasters", "*.sr;*.ras"),
				("TIFF files", "*.tiff;*.tif")
			), initialdir=init_dir, parent=self.root)
			if selection != "":
				self.file_ent.delete(0, tk.END)
				self.file_ent.insert(0, selection.replace("/", "\\"))
				self.file_ent.xview_moveto(1)

	def convert_click(self):
		if not self.processing:
			self.processing = True
			self.update_ui()
			self.root.update_idletasks()

			open_path = self.file_ent.get()

			if os.path.isfile(open_path):
				self.status_line_lbl.config(text="Converting...")
				self.root.update_idletasks()
				og_img = cv2.imread(open_path, cv2.IMREAD_COLOR)  # try to read as image

				if og_img is not None:
					# successfully read as image
					save_path = self.get_save_path(open_path, video=False)
					if save_path != "":
						start_time = time.time()
						self.img_cvt_thread = threading.Thread(target=self.img_cvt, args=(og_img, save_path, start_time), daemon=True)
						self.img_cvt_thread.start()
					else:
						self.processing = False
						self.update_ui()
						self.status_line_lbl.config(text="Ready")
						self.root.update_idletasks()
				else:
					longest_video_stream = None
					length_of_longest = 0
					try:
						probe_info = ffmpeg.probe(open_path, cmd=self.ffprobe_path)
						for i in range(len(probe_info["streams"])):
							try:
								if (probe_info["streams"][i]["codec_type"] == "video"
									and float(probe_info["streams"][i]["bit_rate"]) > 0
									and probe_info["streams"][i]["width"] * probe_info["streams"][i]["height"] != 0
									and float(probe_info["streams"][i]["duration"]) >= 0.25
									and float(probe_info["streams"][i]["duration"]) >= length_of_longest):

									longest_video_stream = i
									length_of_longest = float(probe_info["streams"][i]["duration"])
							except KeyError:
								pass
					except Exception:
						pass
					del length_of_longest

					if longest_video_stream is not None:
						save_path = self.get_save_path(open_path, video=True)
						if save_path != "":
							self.processing_video = True
							self.update_ui()
							self.root.update_idletasks()
							start_time = time.time()
							self.vid_cvt_thread = threading.Thread(target=self.vid_cvt, args=(open_path, longest_video_stream, save_path, start_time), daemon=True)
							self.vid_cvt_thread.start()
						else:
							self.processing = False
							self.update_ui()
							self.status_line_lbl.config(text="Ready")
							self.root.update_idletasks()
					else:
						showerror(title="File Format Error!", message="The specified file's format is not supported!", parent=self.root)
						self.processing = False
						self.update_ui()
						self.status_line_lbl.config(text="Error")
						self.root.update_idletasks()
			else:
				showerror(title="File Not Found!", message="The specified file was not found!", parent=self.root)
				self.processing = False
				self.update_ui()
				self.status_line_lbl.config(text="Error")
				self.root.update_idletasks()
		elif self.processing_video:  # stop clicked
			self.processing = False
			self.processing_video = False
			self.job_id += 1
			self.update_ui()
			self.root.update_idletasks()

	def preview_click(self):
		try:
			if not self.processing:
				self.processing = True
				self.update_ui()
				self.root.update_idletasks()

				open_path = self.file_ent.get()
				if os.path.isfile(open_path):
					self.status_line_lbl.config(text="Generating...")
					self.root.update_idletasks()
					og_img = cv2.imread(open_path, cv2.IMREAD_COLOR)  # try to read as image
					if og_img is not None:  # if it's an image
						self.preview_img_cvt_thread = threading.Thread(target=self.preview_img_cvt, args=(og_img,), daemon=True)
						self.preview_img_cvt_thread.start()
					else:  # if it's not an image
						longest_video_stream = None
						length_of_longest = 0
						try:
							probe_info = ffmpeg.probe(open_path, cmd=self.ffprobe_path)
							for i in range(len(probe_info["streams"])):
								try:
									if (probe_info["streams"][i]["codec_type"] == "video"
										and float(probe_info["streams"][i]["bit_rate"]) > 0
										and probe_info["streams"][i]["width"] * probe_info["streams"][i]["height"] != 0
										and float(probe_info["streams"][i]["duration"]) >= 0.25
										and float(probe_info["streams"][i]["duration"]) >= length_of_longest):

										longest_video_stream = i
										length_of_longest = float(probe_info["streams"][i]["duration"])
								except KeyError:
									pass
						except Exception:
							pass

						# if there is a video stream in the file
						if longest_video_stream is not None:
							self.preview_vid_cvt_thread = threading.Thread(target=self.preview_vid_cvt, args=(open_path, longest_video_stream, length_of_longest), daemon=True)
							self.preview_vid_cvt_thread.start()
						else:
							showerror(title="File Format Error!", message="The specified file's format is not supported!")
							self.processing = False
							self.update_ui()
							self.status_line_lbl.config(text="Error")
				else:
					showerror(title="File Not Found!", message="The specified file was not found!")
					self.processing = False
					self.update_ui()
					self.status_line_lbl.config(text="Error")
		except Exception:  # app was closed while processing
			pass

	def update_ui(self):
		if self.processing:
			self.file_ent.config(state=tk.DISABLED, highlightcolor="black", highlightbackground="black")
			self.browse_btn.config(highlightcolor="black", highlightbackground="black", cursor="arrow")
			self.color_front_lbl.config(cursor="arrow")
			self.color_back_lbl.config(cursor="arrow")
			self.fontscale_ent.config(state=tk.DISABLED, highlightcolor="black", highlightbackground="black")
			self.preview_btn.config(highlightcolor="black", highlightbackground="black", highlightthickness=1, cursor="arrow")
			if self.processing_video:
				self.convert_btn.config(text="Stop", highlightcolor="red", highlightbackground="red", cursor="hand2")
			else:
				self.convert_btn.config(text="Convert", highlightcolor="black", highlightbackground="black", cursor="arrow", highlightthickness=1)
		else:
			self.file_ent.config(state=tk.NORMAL, highlightcolor="green", highlightbackground="green")
			self.browse_btn.config(highlightcolor="green", highlightbackground="green", cursor="hand2")
			self.color_front_lbl.config(cursor="hand2")
			self.color_back_lbl.config(cursor="hand2")
			self.fontscale_ent.config(state=tk.NORMAL, highlightcolor="green", highlightbackground="green")
			self.preview_btn.config(highlightcolor="green", highlightbackground="green", cursor="hand2")
			self.convert_btn.config(text="Convert", highlightcolor="green", highlightbackground="green", cursor="hand2")

	def img_cvt(self, og_img, save_path, start_time):
		try:
			try:
				font_scale_val = float(self.fontscale_ent.get())
			except ValueError:
				font_scale_val = 0.001
			if font_scale_val == 0:
				font_scale_val = 0.001

			converted_img = cv2.cvtColor(frame_to_ascii(og_img, font_scale_val, self.front_color, self.back_color), cv2.COLOR_RGB2BGR)

			cv2.imwrite(save_path, converted_img, [cv2.IMWRITE_PNG_COMPRESSION, 9])

			if not self.processing:  # if the app was closed while processing
				try:
					os.remove(save_path)
				except OSError:
					pass

			self.processing = False
			self.status_line_lbl.config(text=f"Completed ({round(time.time() - start_time, 3)} s)")
			self.update_ui()
		except Exception:  # app was closed while processing
			pass

	def vid_cvt(self, video_path, stream_idx, save_path, start_time):
		try:
			curr_job_id = self.job_id

			try:
				probe_info = ffmpeg.probe(video_path, cmd=self.ffprobe_path)
				try:
					width = probe_info["streams"][stream_idx]["width"]
					height = probe_info["streams"][stream_idx]["height"]
					fps = eval(probe_info["streams"][stream_idx]["avg_frame_rate"])
					pixel_format = probe_info["streams"][stream_idx]["pix_fmt"]
					og_codec = probe_info["streams"][stream_idx]["codec_name"]
					num_of_frames = int(probe_info["streams"][stream_idx]["nb_frames"])
				except KeyError:
					raise Exception
			except Exception:
				showerror(title="File Format Error!", message="The specified file's format is not supported!", parent=self.root)
				self.processing = False
				self.processing_video = False
				self.update_ui()
				return

			try:
				font_scale_val = float(self.fontscale_ent.get())
			except ValueError:
				font_scale_val = 0.001
			if font_scale_val == 0:
				font_scale_val = 0.001

			process_in = (ffmpeg
			              .input(video_path, r=fps)[str(stream_idx)]
			              .output('pipe:', format='rawvideo', pix_fmt='rgb24', r=fps)
			              .global_args("-loglevel", "quiet")
			              .run_async(pipe_stdout=True, cmd=self.ffmpeg_path)
			              )
			process_out = (ffmpeg
			               .input('pipe:', format='rawvideo', pix_fmt='rgb24', s=f'{width}x{height}', r=fps)
			               .output(ffmpeg.input(video_path, r=fps, vn=None), save_path, pix_fmt=pixel_format, r=fps,
			                       vcodec=og_codec, codec="copy")
			               .global_args("-loglevel", "quiet")
			               .overwrite_output()
			               .run_async(pipe_stdin=True, cmd=self.ffmpeg_path)
			               )

			num_of_cpus = os.cpu_count()
			self.status_line_lbl.config(text="Converting... 0.0 %")
			self.root.update_idletasks()

			broken = False
			with multiprocessing.Pool(processes=num_of_cpus) as pool:
				queue = collections.deque()
				ended = False
				count_frames = 0
				while True:
					if self.job_id != curr_job_id:
						broken = True
						break
					elif len(queue) < 2 * num_of_cpus and not ended:
						try:
							in_bytes = process_in.stdout.read(width * height * 3)
						except OSError:
							in_bytes = b""

						if not in_bytes:
							ended = True
						else:
							in_frame = np.frombuffer(in_bytes, np.uint8).reshape([height, width, 3])
							queue.append(pool.apply_async(frame_to_ascii, args=(in_frame, font_scale_val, self.front_color, self.back_color)))
					elif len(queue) == 0 and ended:
						break
					else:
						out_frame = queue.popleft().get()
						process_out.stdin.write(out_frame.astype(np.uint8).tobytes())
						count_frames += 1
						self.status_line_lbl.config(text=f"Converting... {round((count_frames / num_of_frames) * 100, 1)} %")
						self.root.update_idletasks()

			process_out.stdin.close()
			process_in.stdout.close()
			process_out.wait()
			process_in.wait()
			if broken:  # if the app was closed while processing
				try:
					os.remove(save_path)
				except OSError:
					pass

				self.status_line_lbl.config(text="Stopped")
				self.root.update_idletasks()
			else:
				self.processing = False
				self.processing_video = False
				self.status_line_lbl.config(text=f"Completed ({round(time.time() - start_time, 3)} s)")
				self.update_ui()
		except Exception:  # app was closed while processing
			pass

	def preview_img_cvt(self, og_img):
		try:
			try:
				try:
					font_scale_val = float(self.fontscale_ent.get())
				except ValueError:
					font_scale_val = 0.001
				if font_scale_val == 0:
					font_scale_val = 0.001

				preview_img = frame_to_ascii(og_img, font_scale_val, self.front_color, self.back_color)
				height, width, _ = preview_img.shape

				width_fx = (self.root.winfo_screenwidth() * 0.8) / width
				height_fx = (self.root.winfo_screenheight() * 0.8) / height
				shrink_f = min(width_fx, height_fx)
				if shrink_f < 1:
					preview_img = cv2.resize(preview_img, (0, 0), fx=shrink_f, fy=shrink_f, interpolation=cv2.INTER_AREA)
				height, width, _ = preview_img.shape

				self.status_line_lbl.config(text="Preview")
				self.root.update_idletasks()

				preview_window = tk.Toplevel(self.root)
				preview_window.title("Preview")
				preview_window.geometry(f"{width}x{height}"
				                        f"+{(self.root.winfo_screenwidth() // 2) - (width // 2)}"
				                        f"+{(self.root.winfo_screenheight() // 2) - (height // 2)}")
				preview_image_object = PIL_Image.fromarray(preview_img)
				preview_image_object = PIL_ImageTk.PhotoImage(image=preview_image_object)
				preview_widget = tk.Label(preview_window, image=preview_image_object)
				preview_widget.place(x=0, y=0, width=width, height=height)
				preview_window.iconbitmap(self.resource_path("resources/convert-icon.ico"))
				preview_window.grab_set()
				preview_window.resizable(False, False)
				preview_window.focus_force()
				preview_window.wait_window()

				self.status_line_lbl.config(text="Ready")
			except Exception:
				self.status_line_lbl.config(text="Error")
			finally:
				self.processing = False
				self.update_ui()
		except Exception:  # app was closed while processing
			pass

	def preview_vid_cvt(self, video_path, stream_idx, duration):
		try:
			try:
				try:
					font_scale_val = float(self.fontscale_ent.get())
				except ValueError:
					font_scale_val = 0.001
				if font_scale_val == 0:
					font_scale_val = 0.001

				out_img, err = (ffmpeg
				                .input(video_path, ss=(random.random() * 0.6 + 0.2) * duration)[str(stream_idx)]  # random time between 20% and 80% of the video
				                .output('pipe:', vframes=1, format='image2pipe', vcodec="png")
				                .run(capture_stdout=True, capture_stderr=True, cmd=self.ffmpeg_path)
				                )

				preview_og_image = cv2.imdecode(np.asarray(bytearray(out_img), dtype="uint8"), cv2.IMREAD_COLOR)
				height, width, _ = preview_og_image.shape

				preview_img = frame_to_ascii(preview_og_image, font_scale_val, self.front_color, self.back_color)
				width_fx = (self.root.winfo_screenwidth() * 0.8) / width
				height_fx = (self.root.winfo_screenheight() * 0.8) / height
				shrink_f = min(width_fx, height_fx)
				if shrink_f < 1:
					preview_img = cv2.resize(preview_img, (0, 0), fx=shrink_f, fy=shrink_f, interpolation=cv2.INTER_AREA)

				height, width, _ = preview_img.shape

				self.status_line_lbl.config(text="Preview")
				self.root.update_idletasks()

				preview_window = tk.Toplevel(self.root)
				preview_window.title("Preview")
				preview_window.geometry(f"{width}x{height}"
				                        f"+{(self.root.winfo_screenwidth() // 2) - (width // 2)}"
				                        f"+{(self.root.winfo_screenheight() // 2) - (height // 2)}")
				preview_image_object = PIL_Image.fromarray(preview_img)
				preview_image_object = PIL_ImageTk.PhotoImage(image=preview_image_object)
				preview_widget = tk.Label(preview_window, image=preview_image_object)
				preview_widget.place(x=0, y=0, width=width, height=height)
				preview_window.iconbitmap(self.resource_path("resources/convert-icon.ico"))
				preview_window.grab_set()
				preview_window.resizable(False, False)
				preview_window.focus_force()
				preview_window.wait_window()

				self.status_line_lbl.config(text="Ready")
			except Exception:
				self.status_line_lbl.config(text="Error")
			finally:
				self.processing = False
				self.update_ui()
		except Exception:  # app was closed while processing
			pass

	@staticmethod
	def resource_path(relative_path=""):
		""" Get absolute path to resource, works for dev and for PyInstaller """
		try:
			# PyInstaller creates a temp folder and stores path in _MEIPASS
			base_path = sys._MEIPASS
		except Exception:
			base_path = os.path.abspath(".")
		return os.path.join(base_path, relative_path)

	@staticmethod
	def validate_fontscale(full_text):
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


if __name__ == "__main__":
	multiprocessing.freeze_support()
	App()
