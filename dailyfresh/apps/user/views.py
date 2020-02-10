from django.shortcuts import render, redirect
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
# from django.core.mail import send_mail
import re
from django.views.generic import View
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from utils.mixin import LoginRequiredMixin
from celery_tasks.tasks import send_register_active_email
from django_redis import get_redis_connection
from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo, OrderGoods
from apps.user.models import User, Address


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
	'''显示登录页面'''
	def get(self, request):
		# 显示登录页面
		# 判断是否记住密码
		if 'username' in request.COOKIES:
			username = request.COOKIES.get('username')  # request.COOKIES['username']
			checked = 'checked'
		else:
			username = ''
			checked = ''
		return render(request, 'login.html', {'username': username, 'checked': checked})

	'''处理登录业务'''
	def post(self, request):
		# 接受数据
		username = request.POST.get('username')
		password = request.POST.get('pwd')
		# 校验数据
		if not all([username, password]):
			return render(request, 'login.html', {'errmsg': '用户名或者密码不能为空'})
		# 处理数据：业务操作
		user = authenticate(username=username, password=password)
		if user is not None:
			# 用户验证通过
			print('user.is_active = ', user.is_active)
			if user.is_active:
				# 用户已经激活
				login(request, user)
				# 获取登录后要跳转到的页面
				next_url = request.GET.get('next', reverse('goods:index'))

				print(request.GET.get('next', ''))
				print('next_url = ', next_url)
				response = redirect(next_url)  # HttpResponseRedirect
				# 获取＂记住用户名＂
				remember = request.POST.get('remember')
				# 判断是否勾选
				if remember == 'on':
					# 勾选：设置cookie
					response.set_cookie('username', username, max_age=7*24*3600)
				else:
					# 没有勾选：设置cookie，取消记住
					response.delete_cookie('username')

				return response
			else:
				# 用户未激活，指引用户去激活页面（目前激活页面不存在）
				return redirect(reverse('user:register'))
		else:
			# 用户不存在
			return render(request, 'login.html', {'errmsg': '用户名或者密码不正确'})
		# 响应数据


class LogoutView(View):
	def get(self, request):
		logout(request)
		return redirect(reverse('goods:index'))


# /user
class UserInfoView(LoginRequiredMixin, View):
	'''用户信息中心'''
	def get(self, request):
		# page=user
		# 获取个人信息
		user = request.user
		address = Address.objects.get_default_address(user)
		# 获取最近浏览商品信息
		# from redis import StrictRedis
		# str = StrictRedis(host='localhost', port='6379', db=9)
		con = get_redis_connection('default')

		history_key = 'history_%d'%user.id
		# 获取用户最新浏览的５个商品的ID
		sku_ids = con.lrange(history_key, 0, 4)

		goods_li = []
		for pid in sku_ids:
			goods = GoodsSKU.objects.get(id=pid)
			goods_li.append(goods)

		# 组织上下文
		context = {
			'page': 'user',
			'address': address,
			'goods_li': goods_li
		}
		return render(request, 'user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
	'''用户订单信息页面'''
	def get(self, request, page):
		# page = order
		# 获取用户的订单信息
		user = request.user
		orders = OrderInfo.objects.filter(user=user)

		# 遍历获取订单商品的信息
		for order in orders:
			# 根据order_id查询订单商品信息
			order_skus = OrderGoods.objects.filter(order_id=order.order_id)

			for order_sku in order_skus:
				# 计算小计
				amount = order_sku.count * order_sku.price
				# 动态给order_sku添加小计属性
				order_sku.amount = amount

			# 动态给order增加属性，保存订单商品信息
			order.order_skus = order_skus

		# 分页
		paginator = Paginator(orders, 1)

		# 获取第page页的内容
		try:
			page = int(page)
		except Exception as e:
			page = 1

		if page > paginator.num_pages or page <= 0:
			page = 1

		# 获取第page页的page实例对象
		order_page = paginator.page(page)

		# todo: 进行页码的控制，页面上最多显示5个页码
		# 1.总页数小于5页，那么分页处则显示所有页面
		# 2.如果需要显示的页面是最前三页中的一页,则显示前5页，一共5个页面
		# 3.如果需要显示的页面是最后三页中的一页,则显示后5页，一共5个页面
		# 4.其他情况：显示当前页的前2页，当前页面，当前页的后2页，一共5个页面

		num_pages = paginator.num_pages
		if num_pages < 5:
			pages = range(1, num_pages + 1)
		elif page <= 3:
			pages = range(1, 6)
		elif num_pages - page <= 2:
			pages = range(num_pages - 4, num_pages + 1)
		else:
			pages = range(page - 2, page + 3)

		context = {
			'order_page': order_page,
			'pages': pages,
			'page': 'order'
		}
		return render(request, 'user_center_order.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
	'''用户地址信息页面'''
	# page = address
	def get(self, request):
		user = request.user
		# try:
		# 	address = Address.objects.get(user=user, is_default=True)
		# except Address.DoesNotExist:
		# 	address = None
		# 获取用户信息
		address = Address.objects.get_default_address(user)
		return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

	def post(self, request):
		receiver = request.POST.get('receiver')
		addr = request.POST.get('addr')
		zip_code = request.POST.get('zip_code')
		phone = request.POST.get('phone')
		user = request.user

		if not all([receiver, addr, phone]):
			return render(request, 'user_center_site.html', {'errmsg': '填写数据不完整，请检查'})

		if not re.match(r"^1(3|4|5|6|7|8|9)\d{9}$", phone):
			return render(request, 'user_center_site.html', {'errmsg': '填写手机号码有误'})

		# try:
		# 	address = Address.objects.get(user=user, is_default=True)
		# except Address.DoesNotExist:
		# 	address = None
		address = Address.objects.get_default_address(user)

		if address:
			is_default = False
		else:
			is_default = True

		Address.objects.create(
			user=user,
			receiver=receiver,
			addr=addr,
			zip_code=zip_code,
			phone=phone,
			is_default=is_default
		)
		return redirect(reverse('user:address'))


