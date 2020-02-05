# -*-coding:utf-8-*-
# 定义索引类, 此文件名为固定的
from haystack import indexes
from apps.goods.models import GoodsSKU


class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    # document=True:　说明这是一个索引字段
    # use_template：　说明你根据哪些字段建立索引字段,＝True把这个说明放在一个文件中
    text = indexes.CharField(document=True, use_template=True, template_name='search/indexes/goods/goodssku_text.txt')
    # author = indexes.CharField(model_attr='user')
    # pub_date = indexes.DateTimeField(model_attr='pub_date')

    def get_model(self):
        return GoodsSKU

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        # return self.get_model().objects.filter(pub_date__lte=datetime.datetime.now())
        return self.get_model().objects.all()


