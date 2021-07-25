import json
import subprocess
from selenium import webdriver
import redis
from common.utility import Utility
from common.mapping import Mapping
from common.global_logger import logger
from selenium.webdriver import ActionChains
from selenium.common.exceptions import NoSuchElementException
import socket
class SuperBrowser(object):

    # 基础配置
    utils = Utility()
    config = utils.config
    # 初始化Redis服务
    ip='127.0.0.1'
    password='123456'
    obj_redis = redis.Redis(host=ip,password=password,port=6379,db=1)

    # 获取业务类型
    business_type = config.get('business_type')
    logger.info("business_type: %s" % business_type)

    # 指定使用英语
    __LANGUAGE = config.get('language')

    # ----------------------------------------->> Socket通信地址端口
    host = config.get('socket_host')
    port = int(config.get('socket_port'))
    logger.info('socket > host: %s, port: %s' % (host, port))
    # ----------------------------------------->> 请求紫鸟超级浏览器API方法
    __GET_BROWSER_LIST = "getBrowserList"         # 获取店铺列表
    __START_BROWSER = "startBrowser"              # 启动店铺(主程序)
    __STOP_BROWSER = "stopBrowser"                # 关闭店铺窗口
    __GET_BROWSER_ENV_INFO = "getBrowserEnvInfo"  # 启动店铺(webdriver)
    __HEARTBEAT = "heartbeat"                     # 非必要接口，只是用于保活Socket连接
    __EXIT = "exit"                               # 正常退出超级浏览器主进程，会自动关闭已启动店铺并保持店铺cookie等信息。

    def __init__(self):
        logger.info("初始化Socket连接...")
        logger.info("启动紫鸟浏览器......")

        self.buf_size = int(self.config.get('socket_buf_size'))
        self.IS_HEADLESS = self.config.get('browser_is_headless')     # 浏览器是否启用无头模式 false 否、true 是

        # 获取紫鸟·超级浏览器安装路径
        path_super_browser = self.config.get('path_super_browser')
        cmd = "{} --run_type=web_driver --socket_port={}".format(path_super_browser, self.port)
        print(cmd)
        #subprocess.Popen(cmd)
        try:
            # ------------------------------创建套接字通道
            self.address = (self.host, self.port)
            print(self.address)

            self.tcpCliSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # 创建套接字
            self.tcpCliSock.connect(self.address)           # 主动初始化TCP服务器连接
        except ConnectionRefusedError as e:
            logger.error(e)
            #subprocess.Popen('taskkill /f /im superbrowser.exe')
        except Exception as e:
            logger.error(e)

    def browser_api(self, action, args=None):
        """
        紫鸟·超级浏览器API
        :param action: 方法
        :param args: 可选参数
        :return:
        """
        REQUEST_ID = "0123456789"  # 全局唯一标识
        user_info = json.dumps({   # 用户信息
            "company": self.config.get('browser_company_name'),
            "username": self.config.get('browser_username'),
            "password": self.config.get('browser_password')
        })
        # 默认为获取店铺列表
        common = {"userInfo": user_info, "action": self.__GET_BROWSER_LIST, "requestId": REQUEST_ID}
        if action == self.__START_BROWSER or action == self.__GET_BROWSER_ENV_INFO or action == self.__STOP_BROWSER:
            common['browserOauth'] = args['browserOauth']
            common['isHeadless'] = args['isHeadless']
        common['action'] = action
        return common  

    def socket_communication(self, params):
        """
        Socket通信
        :param params: 参数对象
        :return:
        """
        try:
            self.address = (self.host, self.port)
     
            phone=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            phone.connect(('127.0.0.1',21591)) #拨通电话

            phone.send('hello'.encode('utf-8')) #发消息
            print(2222)
            back_msg=phone.recv(1024)
            print(back_msg)

            self.tcpCliSock = socket(socket.AF_INET, socket.SOCK_STREAM)  # 创建套接字
            self.tcpCliSock.connect(self.address)   
            args = (str(params) + '\r\n').encode('utf-8')
            #args = json.loads(params.decode())
            # 将 string 中的数据发送到连接的套接字
            self.tcpCliSock.send(args)
            print(self.tcpCliSock)
            res = self.tcpCliSock.recv(2014)
            #print('recv:',res.decode()) #输出我接收的信息
            print(res)
            return json.loads(res)
        except ConnectionResetError as e:
            logger.warning("ConnectionResetError: %s" % e)
            logger.info("socket 连接已关闭")
        except Exception as e:
            logger.error("socket_communication error: %s" % e)
        pass

    # 举个栗子
    def browser_list(self):
        """
        获取店铺列表
        这里采用Redis管理店铺，为了后期分布式部署准备。
        :return:
        """
        logger.info("")
        logger.info("获取店铺列表.")
        shop_list_params = self.browser_api(self.__GET_BROWSER_LIST)
        print(shop_list_params)
        shop_info = self.socket_communication(shop_list_params)
        if hasattr(shop_info, 'statusCode') and shop_info['statusCode'] == 0:
            browser_size = len(shop_info['browserList'])
            logger.info("目前店铺总数: %s, 正在记录店铺信息...,请稍等." % browser_size)
            current_time = Utility.curr_time()
            for index, browser in enumerate(shop_info['browserList']):
                index += 1
                # site_id 对应的值
                browser['site_name'] = Mapping.SiteIdExplain(browser['siteId'])
                browserOauth = browser['browserOauth']
                if browser['isExpired'] is False:

                    # 记录店铺的数据
                    key_completed = self.config.get('r_amz_shops_completed')
                    key_inProgress = self.config.get('r_amz_shops_inProgress')
                    params = json.dumps({
                        "type": self.business_type,
                        "browserOauth": browserOauth,
                        "browserName": browser['browserName'],
                        "browserIp": browser['browserIp'],
                        "siteId": browser['siteId'],
                        "site_name": browser['site_name'],
                        "isExpired": browser['isExpired']
                    })

                    # 检索该店铺数据是否已采集完成？
                    is_sismember = self.obj_redis.sismember(key_completed, params)
                    if is_sismember:
                        logger.info('%s, 已采集完成.' % browserOauth)
                    else:
                        self.obj_redis.sadd(key_inProgress, params)
                    pass
                else:
                    # 代理IP过期告警...
                    title = "Amazon·货件状态"   # 悬浮标题
                    iphone = self.config.get('ding_talk_iphone')  # @的指定人
                    spider_name = self.config.get('sn_v_shipment_status')     # 应用名称
                    browserName = browser['browserName']    # 店铺
                    site_name = browser['site_name']    # 所属平台
                    browserIp = browser['browserIp']    # 代理IP
                    cloud_server = self.config.get('cloud_server_name')  # 云服务器名称
                    # 通知内容
                    inform_content = "##### @{} Amazon·货件状态*>应用名称: {}*>店铺: {}*>所属平台: {}*>代理IP: {}*>" \
                                     "服务器: {}*>当前时间: {}*>店铺ID: {}*>是否过期:" \
                                     " <font color=#FFOOOO size=3 face='隶书'>代理IP已过期</font>*>" \
                        .format(iphone, spider_name, browserName, site_name, browserIp,
                                cloud_server, current_time, browserOauth).replace('*', '\n\n')
                    self.utils.ding_talk_robot(1, title, inform_content, [iphone], False)
                    self.utils.sleep_message(5, "间歇....")
                pass
            pass
        else:
            logger.warning("statusCode:%s" % shop_info)
            # logger.warning("statusCode:%s, err: %s" % (shop_info['statusCode'], shop_info['err']))
        pass