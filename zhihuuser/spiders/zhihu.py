# -*- coding: utf-8 -*-
import json

from scrapy import Spider, Request
from zhihuuser.items import CommentItem, UserItem


class ZhihuSpider(Spider):
    name = "zhihu"
    allowed_domains = ["www.zhihu.com"]
    offset = 0
    start_user = 'excited-vczh'  # 开始的url

    # 查询用户信息的url，在format中由参数传入
    user_url = 'https://www.zhihu.com/api/v4/members/{user}?include={include}' #{ }括号内为变量，可以在后面传入
    # 查询用户信息的参数，传入format中构造查询url
    user_query = 'locations,employments,gender,educations,business,voteup_count,thanked_Count,follower_count,following_count,cover_url,following_topic_count,following_question_count,following_favlists_count,following_columns_count,answer_count,articles_count,pins_count,question_count,commercial_question_count,favorite_count,favorited_count,logs_count,marked_answers_count,marked_answers_text,message_thread_token,account_status,is_active,is_force_renamed,is_bind_sina,sina_weibo_url,sina_weibo_name,show_sina_weibo,is_blocking,is_blocked,is_following,is_followed,mutual_followees_count,vote_to_count,vote_from_count,thank_to_count,thank_from_count,thanked_count,description,hosted_live_count,participated_live_count,allow_message,industry_category,org_name,org_homepage,badge[?(type=best_answerer)].topics'

    # 查询用户回答页的url，1个url上有20个回答
    answer_url = 'https://www.zhihu.com/api/v4/members/{user}/answers?include={include}&offset={offset}&limit={limit}'
    answer_query = 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,collapsed_by,suggest_edit,comment_count,can_comment,content,voteup_count,reshipment_settings,comment_permission,mark_infos,created_time,updated_time,review_info,question,excerpt,is_labeled,label_info,relationship.is_authorized,voting,is_author,is_thanked,is_nothelp;data[*].author.badge[?(type=best_answerer)].topics'

    #评论的地址
    comment_url = 'https://www.zhihu.com/api/v4/answers/{answer_id}/root_comments?include={include}&order=normal&limit={limit}&offset={offset}&status=open'
    comment_query = 'data[*].author,collapsed,reply_to_author,disliked,content,voting,vote_count,is_parent_author,is_author'

    # vczh的关注列表页url
    follows_url = 'https://www.zhihu.com/api/v4/members/{user}/followees?include={include}&offset={offset}&limit={limit}'
    follows_query = 'data[*].answer_count,articles_count,gender,follower_count,is_followed,is_following,badge[?(type=best_answerer)].topics'

    # vczh的关注者的url
    followers_url = 'https://www.zhihu.com/api/v4/members/{user}/followers?include={include}&offset={offset}&limit={limit}'
    followers_query = 'data[*].answer_count,articles_count,gender,follower_count,is_followed,is_following,badge[?(type=best_answerer)].topics'

    def start_requests(self):

        yield Request(self.user_url.format(user=self.start_user, include=self.user_query), self.parse_user)

        # vczh的关注者list页面的url，并用parse_follows方法解析
        yield Request(self.follows_url.format(user=self.start_user, include=self.follows_query, limit=20, offset=0),
                      self.parse_follows)
        # 请求vczh的关注者list页面的url，并用parse_followers方法解析
        yield Request(self.followers_url.format(user=self.start_user, include=self.followers_query, limit=10, offset=10),
                      self.parse_followers)

    def parse_user(self, response):
        result = json.loads(response.text)
        # 用parse_answer方法，解析轮子哥第1页的回答
        yield Request(self.answer_url.format(user=result.get('url_token'), include=self.answer_query, limit=20, offset=0),
                      self.parse_answer)

        yield Request(   # 获取user关注的用户，他们的关注者页面，用parse_follows方法解析
            self.follows_url.format(user=result.get('url_token'), include=self.follows_query, limit=20, offset=0),
            self.parse_follows)
        yield Request(                 # 获取user的粉丝list页面，用parse_followers方法解析
            self.followers_url.format(user=result.get('url_token'), include=self.followers_query, limit=20, offset=0),
            self.parse_followers)

    def parse_answer(self, response): # 用parse_answer方法，解析轮子哥第1页的回答，递归解析后续页的回答
        results = json.loads(response.text)  # result是回答问题页的list，1页有20个问题
        if 'data' in results.keys(): #
            for result in results.get('data'):  # 在json字符串中遍历data对应的list中各行值,对这20个回答分别解析
                answer_id = result.get('id')   # 找到每一个问题对应的id
                yield Request(                 # 遍历20个回答，依次解析评论
                    self.comment_url.format(answer_id=str(answer_id), include=self.comment_query,limit=20, offset=0),
                    self.parse_comment)

        if 'paging' in results.keys() and results.get('paging').get('is_end') == False:  # 关注列表未到末页，则用parse_follows()解析关注列表的下一页
            # next_page = results.get('paging').get('next') #answer默认的next页面打不开
            # 自己组装next页面
            self.offset += 20
            yield Request(self.answer_url.format(user=self.start_user, include=self.answer_query, limit=20, offset=self.offset),
                          self.parse_answer)



    def parse_comment(self, response):  # 针对某一次回答，解析该回答下的所有评论
        results = json.loads(response.text)
        item = CommentItem()  # 创建item对象

        for comment_row_i in results.get('data'):
            for field in item.fields:  # item.fields是items.py中所有已设定的field的名称，如id，name，avatar_url等
                if field in comment_row_i.keys():  # result.keys是json对象的key，如id，name，avatar_url等
                    item[field] = comment_row_i[field]  #
                    # print("-------------------")
                    # print(field, ' : ', item[field])
            yield item

        if 'paging' in results.keys() and results.get('paging').get('is_end') == False:  # 关注列表未到末页，则用parse_follows()解析关注列表的下一页
            next_page = results.get('paging').get('next')  # answer默认的next页面打不开
            yield Request(next_page,
                          self.parse_comment)


    def parse_follows(self, response): #在解析的页面中，找vczh关注的用户列表，并解析
        results = json.loads(response.text)
        if 'data' in results.keys():
            for result in results.get('data'): #在json字符串中遍历data对应的list中各行值
                yield Request(self.user_url.format(user=result.get('url_token'), include=self.user_query), #爬取关注列表中的用户信息
                              self.parse_user)

        if 'paging' in results.keys() and results.get('paging').get('is_end') == False: #关注列表未到末页，则用parse_follows()解析关注列表的下一页
            next_page = results.get('paging').get('next')
            yield Request(next_page,
                          self.parse_follows)

    def parse_followers(self, response):
        results = json.loads(response.text)

        if 'data' in results.keys():
            for result in results.get('data'):
                yield Request(self.user_url.format(user=result.get('url_token'), include=self.user_query),
                              self.parse_user)

        if 'paging' in results.keys() and results.get('paging').get('is_end') == False:
            next_page = results.get('paging').get('next')
            yield Request(next_page,
                          self.parse_followers)
