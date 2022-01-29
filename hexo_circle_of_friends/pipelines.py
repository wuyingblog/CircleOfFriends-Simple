# -*- coding:utf-8 -*-

import leancloud
import datetime
import settings
import sys
import re
from scrapy.exceptions import DropItem


class HexoCircleOfFriendsPipeline:
    def __init__(self):
        self.friend_info = [] # 需最后上传

        self.nonerror_data = set() # 未失联友链link集合

        self.total_post_num = 0
        self.total_friend_num = 0
        self.err_friend_num = 0
    
    def open_spider(self, spider):
        leancloud.init(sys.argv[1], sys.argv[2])
        self.Friendslist = leancloud.Object.extend('friend_list')
        self.Friendspoor = leancloud.Object.extend('friend_poor')
        self.query_friendslist()
        self.query_friendspoor()
        # 友链清洗
        for query_j in self.query_friend_list:
            delete = self.Friendslist.create_without_data(query_j.get('objectId'))
            delete.destroy()

    def process_item(self, item, spider):
        if "descr" in item.keys():
            self.friend_info.append(item)
        elif "title" in item.keys():
            self.nonerror_data.add(item["name"])
            # rss创建时间保留
            for query_item in self.query_post_list:
                if query_item.get("link") == item["link"]:
                    item["created"] = min(item['created'], query_item.get('created'))
                    delete = self.Friendspoor.create_without_data(query_item.get('objectId'))
                    delete.destroy()
            self.friendpoor_push(item)
        return item

    def close_spider(self,spider):
        self.friendlist_push()
        self.outdate_clean(settings.OUTDATE_CLEAN)
        print("----------------------")
        print("友链总数 : %d" % self.total_friend_num)
        print("失联友链数 : %d" % self.err_friend_num)
        print("共 %d 篇文章" % self.total_post_num)
        print("done!")

    # 文章数据查询
    def query_friendspoor(self):
        try:
            query = self.Friendspoor.query
            query.select('title', 'created', 'link', 'updated')
            query.limit(1000)
            self.query_post_list = query.find()
            # print(self.query_post_list)
        except:
            self.query_post_list=[]
    
    # 友链数据查询
    def query_friendslist(self):
        try:
            query = self.Friendslist.query
            query.select('name', 'link', 'avatar', 'error')
            query.limit(1000)
            self.query_friend_list = query.find()
        except:
            self.query_friend_list=[]

    # 超时清洗
    def outdate_clean(self,time_limit):
        out_date_post = 0
        for query_i in self.query_post_list:
            time = query_i.get('time')
            query_time = datetime.datetime.strptime(time, "%Y-%m-%d")
            if (datetime.datetime.today() - query_time).days > time_limit:
                delete = self.Friendspoor.create_without_data(query_i.get('objectId'))
                out_date_post += 1
                delete.destroy()

    # 友链数据上传
    def friendlist_push(self):
        for item in enumerate(self.friend_info):
            friendlist = self.Friendslist()
            friendlist.set('name', item["name"])
            friendlist.set('link', item["link"])
            friendlist.set('avatar', item["avatar"])
            friendlist.set('descr', item["descr"])
            if item[0] in self.nonerror_data:
                friendlist.set('error', "false")
            else:
                self.err_friend_num += 1
                print("请求失败，请检查链接： %s" % item[1])
                friendlist.set('error', "true")
            friendlist.save()
            self.total_friend_num+=1

    # 文章数据上传
    def friendpoor_push(self,item):
        friendpoor = self.Friendspoor()
        friendpoor.set('title', item['title'])
        friendpoor.set('created', item['time'])
        friendpoor.set('updated', item['updated'])
        friendpoor.set('link', item['link'])
        friendpoor.set('author', item['name'])
        friendpoor.set('avatar', item['img'])
        friendpoor.set('rule', item['rule'])
        friendpoor.save()
        print("----------------------")
        print(item["name"])
        print("《{}》\n文章发布时间：{}\t\t采取的爬虫规则为：{}".format(item["title"], item["time"], item["rule"]))
        self.total_post_num +=1

class DuplicatesPipeline:
    def __init__(self):
        self.poor_set = set() # posts filter set 用于对文章数据的去重
        self.friend_set = set() # userdata filter set 用于对朋友列表的去重
    
    def process_item(self, item, spider):
        # 上传前本地审核
        if "descr" in item.keys(): # 本地友链重复审查
            #  userdata filter
            link = item["link"]
            if link in self.friend_set:
                raise DropItem("Duplicate found:%s" % link)
            else:
                self.friend_set.add(link)
                return item
        elif "title" in item.keys(): # 本地文章重复审查
            link = item["link"]
            if link in self.poor_set or link=="":
                # 重复数据清洗
                raise DropItem("Duplicate found:%s" % link)
            elif not link.startswith("http"):
                # 链接必须是http开头，不能是相对地址
                raise DropItem("invalid link")
            elif not re.match("^\d+",item["time"]):
                # 时间不是xxxx-xx-xx格式，丢弃
                raise DropItem("invalid time")
            else:
                self.poor_set.add(link)
                return item