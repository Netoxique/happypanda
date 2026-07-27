import logging, uuid, os

import threading
from collections import OrderedDict
from concurrent import futures
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QBrush, QPen

from database import db_constants
import utils
import app_constants

log = logging.getLogger(__name__)
log_i = log.info
log_d = log.debug
log_w = log.warning
log_e = log.error
log_c = log.critical

def _rounded_qimage(qimg, radius):
	r_image = QImage(qimg.width(), qimg.height(), QImage.Format_ARGB32)
	r_image.fill(Qt.transparent)
	p = QPainter()
	pen = QPen(Qt.darkGray)
	pen.setJoinStyle(Qt.RoundJoin)
	p.begin(r_image)
	p.setRenderHint(p.Antialiasing)
	p.setPen(Qt.NoPen)
	p.setBrush(QBrush(qimg))
	p.drawRoundedRect(0, 0, r_image.width(), r_image.height(), radius, radius)
	p.end()
	return r_image

def _task_thumbnail(gallery_or_path, img=None, width=app_constants.THUMB_W_SIZE,
						height=app_constants.THUMB_H_SIZE):
	"""
	"""
	log_i("Generating thumbnail")
	# generate a cache dir if required
	if not os.path.isdir(db_constants.THUMBNAIL_PATH):
		os.mkdir(db_constants.THUMBNAIL_PATH)

	try:
		if not img:
			img_path = utils.get_gallery_img(gallery_or_path)
		else:
			img_path = img
		if not img_path:
			raise IndexError
		for ext in utils.IMG_FILES:
			if img_path.lower().endswith(ext):
				suff = ext # the image ext with dot

		# generate unique file name
		file_name = str(uuid.uuid4()) + ".png"
		new_img_path = os.path.join(db_constants.THUMBNAIL_PATH, (file_name))
		if not os.path.isfile(img_path):
			raise IndexError

		# Do the scaling
		try:
			im_data = utils.PToQImageHelper(img_path)
			image = QImage(im_data['data'], im_data['im'].size[0], im_data['im'].size[1], im_data['format'])
			if im_data['colortable']:
				image.setColorTable(im_data['colortable'])
		except ValueError:
			image = QImage()
			image.load(img_path)
		if image.isNull():
			raise IndexError
		radius = 5
		image = image.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
		r_image = _rounded_qimage(image, radius)
		r_image.save(new_img_path, "PNG", quality=80)
	except IndexError:
		new_img_path = app_constants.NO_IMAGE_PATH

	return new_img_path

def _task_load_thumbnail(ppath, thumb_size):
	if ppath:
		img = QImage(ppath)
		if not img.isNull():
			size = img.size()
			if size.width() != thumb_size[0]:
				# TODO: use _task_thumbnail
				img = _rounded_qimage(img.scaled(thumb_size[0], thumb_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation), 5)
			return img


class _ThumbnailImageCache:
	def __init__(self):
		self._images = OrderedDict()
		self._pending = {}
		self._bytes = 0
		self._limit = 1
		self._lock = threading.RLock()

	@staticmethod
	def _image_bytes(image):
		try:
			return image.sizeInBytes()
		except AttributeError:
			return image.byteCount()

	@staticmethod
	def key(path, thumb_size):
		if not path:
			return None
		normalized = os.path.normcase(os.path.abspath(path))
		try:
			mtime = os.stat(normalized).st_mtime_ns
		except (OSError, TypeError, ValueError):
			mtime = None
		return normalized, mtime, tuple(thumb_size)

	def configure(self, byte_limit):
		with self._lock:
			self._limit = max(1, int(byte_limit))
			self._evict()

	def _evict(self):
		while self._bytes > self._limit and self._images:
			_, image = self._images.popitem(last=False)
			self._bytes -= self._image_bytes(image)

	def get(self, key):
		if key is None:
			return None
		with self._lock:
			stale_keys = [
				cached_key for cached_key in self._images
				if cached_key[0] == key[0] and cached_key[2] == key[2]
				and cached_key[1] != key[1]]
			for stale_key in stale_keys:
				stale = self._images.pop(stale_key)
				self._bytes -= self._image_bytes(stale)
			image = self._images.pop(key, None)
			if image is not None:
				self._images[key] = image
			return image

	def pending(self, key):
		with self._lock:
			return self._pending.get(key)

	def request(self, key, submit):
		with self._lock:
			image = self.get(key)
			if image is not None:
				return image, None, False
			future = self._pending.get(key)
			if future is not None:
				return None, future, False
			future = submit()
			self._pending[key] = future
			return None, future, True

	def track(self, key, future):
		with self._lock:
			self._pending[key] = future

	def complete(self, key, future):
		try:
			image = future.result()
		except Exception:
			image = None
		with self._lock:
			if self._pending.get(key) is not future:
				return
			self._pending.pop(key, None)
			if image is not None and not image.isNull():
				old = self._images.pop(key, None)
				if old is not None:
					self._bytes -= self._image_bytes(old)
				self._images[key] = image
				self._bytes += self._image_bytes(image)
				self._evict()

	def invalidate(self, path=None):
		with self._lock:
			if path is None:
				self._images.clear()
				self._pending.clear()
				self._bytes = 0
				return
			if not path:
				return
			normalized = os.path.normcase(os.path.abspath(path))
			keys = [key for key in self._images if key[0] == normalized]
			for key in keys:
				image = self._images.pop(key)
				self._bytes -= self._image_bytes(image)
			for key in [key for key in self._pending
						if key[0] == normalized]:
				self._pending.pop(key, None)


_THUMBNAIL_IMAGES = _ThumbnailImageCache()


class _ThumbnailCallbackDispatcher(QObject):
	callback = pyqtSignal(object, object, object)

	def __init__(self):
		super().__init__()
		self.callback.connect(self._dispatch)

	@staticmethod
	def _dispatch(method, image, kwargs):
		method(image, **kwargs)


_THUMBNAIL_CALLBACKS = _ThumbnailCallbackDispatcher()

class Executors:
	_thumbnail_exec = futures.ThreadPoolExecutor(3)
	_profile_exec = futures.ThreadPoolExecutor(2)

	@classmethod
	def configure_thumbnail_cache(cls):
		total_kib = (app_constants.THUMBNAIL_CACHE_SIZE[0] *
					 app_constants.THUMBNAIL_CACHE_SIZE[1])
		_THUMBNAIL_IMAGES.configure(total_kib * 1024 * 0.25)
		return max(1, int(total_kib * 0.75))

	@classmethod
	def cached_thumbnail(cls, ppath, thumb_size=app_constants.THUMB_DEFAULT):
		return _THUMBNAIL_IMAGES.get(
			_THUMBNAIL_IMAGES.key(ppath, thumb_size))

	@classmethod
	def invalidate_thumbnail(cls, ppath=None):
		_THUMBNAIL_IMAGES.invalidate(ppath)
	
	@classmethod
	def generate_thumbnail(cls, gallery_or_path, img=None, width=app_constants.THUMB_W_SIZE,
						height=app_constants.THUMB_H_SIZE, on_method=None, blocking=False):
		log_i("Generating thumbnail")
		f = cls._thumbnail_exec.submit(_task_thumbnail, gallery_or_path, img=img, width=width, height=height)
		if on_method:
			f.add_done_callback(on_method)
		if blocking:
			return f.result()
		if not on_method:
			return f

		log_d("Returning future")

	@classmethod
	def load_thumbnail(cls, ppath, thumb_size=app_constants.THUMB_DEFAULT, on_method=None, **kwargs):
		"**kwargs will be passed to on_method"
		key = _THUMBNAIL_IMAGES.key(ppath, thumb_size)
		if key is None:
			f = futures.Future()
			f.set_result(None)
		else:
			image, f, created = _THUMBNAIL_IMAGES.request(
				key, lambda: cls._profile_exec.submit(
					_task_load_thumbnail, ppath, thumb_size))
			if image is not None:
				f = futures.Future()
				f.set_result(image)
			elif created:
				f.add_done_callback(
					lambda completed, cache_key=key:
					_THUMBNAIL_IMAGES.complete(cache_key, completed))
		if on_method:
			def notify(completed):
				try:
					loaded = completed.result()
				except Exception:
					loaded = None
				if loaded is not None:
					_THUMBNAIL_CALLBACKS.callback.emit(
						on_method, loaded, kwargs)
			f.add_done_callback(notify)
		return f


Executors.configure_thumbnail_cache()

