
#%%
from selenium import webdriver
from time import sleep

# 初始化
driver = webdriver.Chrome()
driver.get('https://www.baidu.com') 

# 输入框 id kw  class s_ipt
driver.find_element_by_id('kw').send_keys('虚竹')

driver.find_element_by_id('su').click()
sleep(5)
# 点击 第一个搜索结果 
#//*[@id="1"]/h3/a
# 添加 等待 ，因为 脚本执行太快了
driver.find_element_by_xpath('//*[@id="1"]/h3/a').click()
sleep(5)
driver.close()