from django.shortcuts import render, redirect
from django.urls import reverse
# from django.core.mail import send_mail
from .models import User
import re
from django.views.generic import View
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.conf import settings
from django.http import HttpResponse
from celery_tasks.tasks import send_register_active_email

# user/register
def register(request):
	"""注册"""
	if request.method == 'GET':
		# 显示注册页面
		return render(request, 'register.html')
	else:
		# 处理注册业务
		username = request.POST.get('user_name')
		password = request.POST.get('pwd')
		email = request.POST.get('email')
		allow = request.POST.get('allow')
		# 数据的校验
		if not all([username, password, email]):
			# 数据不完整
			return render(request, 'register.html', {'errmsg': '数据不完整（有数据为空！）'})
		# 校验邮箱
		if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
			# 邮箱有错误
			return render(request, 'register.htnml', {'errmsg': '邮箱有误'})
		if allow != 'on':
			return render(request, 'register.html', {'errmsg': '请同意用户协议'})
		# 校验用户是否存在
		try:
			user = User.objects.get(username=username)
		except User.DoesNotExist:
			user = None

		if user:
			return render(request, 'register.html', {'errmsg': '用户已存在，请更换用户名字'})
		# 业务处理：进行用户注册
		user = User.objects.create_user(username, email, password)
		user.is_active = 0
		user.save()
		# 返回应答
		return redirect(reverse('goods:index'))


# user/register_handle
def register_handle(request):
	"""处理注册"""
	# 接受数据
	username = request.POST.get('user_name')
	password = request.POST.get('pwd')
	email = request.POST.get('email')
	allow = request.POST.get('allow')
	# 数据的校验
	if not all([username, password, email]):
		# 数据不完整
		return render(request, 'register.html', {'errmsg': '数据不完整（有数据为空！）'})
	# 校验邮箱
	if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
		# 邮箱有错误
		return render(request, 'register.htnml', {'errmsg': '邮箱有误'})
	if allow != 'on':
		return render(request, 'register.html', {'errmsg': '请同意用户协议'})
	# 校验用户是否存在
	try:
		user = User.objects.get(username=username)
	except User.DoesNotExist:
		user = None

	if user:
		return render(request, 'register.html', {'errmsg': '用户已存在，请更换用户名字'})
	# 业务处理：进行用户注册
	user = User.objects.create_user(username, email, password)
	user.is_active = 0
	user.save()

	# 返回应答，跳转到首页
	return redirect(reverse('goods:index'))


class RegisterView(View):
	"""注册使用的类"""
	def get(self, request):
		return render(request, 'register.html')

	def post(self, request):
		# 接受数据
		username = request.POST.get('user_name')
		password = request.POST.get('pwd')
		email = request.POST.get('email')
		allow = request.POST.get('allow')
		# 数据的校验
		if not all([username, password, email]):
			# 数据不完整
			return render(request, 'register.html', {'errmsg': '数据不完整（有数据为空！）'})
		# 校验邮箱
		if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
			# 邮箱有错误
			return render(request, 'register.htnml', {'errmsg': '邮箱有误'})
		if allow != 'on':
			return render(request, 'register.html', {'errmsg': '请同意用户协议'})
		# 校验用户是否存在
		try:
			user = User.objects.get(username=username)
		except User.DoesNotExist:
			user = None

		if user:
			return render(request, 'register.html', {'errmsg': '用户已存在，请更换用户名字'})
		# 业务处理：进行用户注册
		user = User.objects.create_user(username, email, password)
		user.is_active = 0
		user.save()

		# 发送激活邮件，包含激活链接：/user/active
		# 激活链接中需要包含用户的身份信息，并且要把身份信息加密处理
		# 加密用户信息，生成token
		serializer = Serializer(settings.SECRET_KEY, 1800)
		info = {'confirm': user.id}
		token = serializer.dumps(info)
		token = token.decode('utf8')
		# # 发邮箱
		# subject = '天天生鲜欢迎信息'
		# message = ''
		# sender = settings.EMAIL_PROM  # 发送人
		# receiver = [email]
		# html_message = '<h1>%s, 欢迎您成为天天生鲜注册会员' \
		#                '</h1>请点击下面链接激活您的账户<br/>' \
		#                '<a href="http://127.0.0.1:8000/user/active/%s">' \
		#                'http://127.0.0.1:8000/user/active/%s' \
		#                '</a>' % (username, token, token)
		#
		# send_mail(subject, message, sender, receiver, html_message=html_message)
		# 找其他人帮助我们发送邮件 celery:异步执行任务
		send_register_active_email.delay(email, username, token)
		# 返回应答
		return redirect(reverse('goods:index'))


class ActiveView(View):
	def get(self, request, token):
		"""进行用户激活"""
		# 进行解密，获取用户信息（通过token）
		serializer = Serializer(settings.SECRET_KEY, 1800)
		# print('token = ', token)
		try:
			info = serializer.loads(token)
			# 获取用户ID
			# print('info = ', info)
			user_id = info['confirm']
			# print('user_id = ', user_id)
			# 根据用户ID获取用户信息
			user = User.objects.get(id=user_id)
			# print('user = ', user)
			user.is_active = 1
			user.save()
			return redirect(reverse('user:login'))
		except SignatureExpired as e:
			return HttpResponse("链接已过期，请重新申请!")


class LoginView(View):
	def get(self, request):
		return render(request, 'login.html')

