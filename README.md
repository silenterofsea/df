# df
1.激活问题：   ａ，激活链接失效时，没有引导到再次激活的页面
            　ｂ，已经激活的用户再次激活时，没有提示
２．注册时：    request.GET.get('next', reverse('goods:index'))
              没有正确获得next的链接
