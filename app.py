import streamlit as st
import pandas as pd
import requests
import time
import json
import re
from datetime import datetime
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Optional
import base64

# 页面配置
st.set_page_config(
    page_title="Shopee评论爬取分析工具",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #ee4d2d;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton button {
        background-color: #ee4d2d;
        color: white;
        font-weight: bold;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 5px;
        transition: all 0.3s;
    }
    .stButton button:hover {
        background-color: #d83b1f;
        transform: scale(1.05);
    }
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .review-card {
        background-color: #f8f9fa;
        border-left: 4px solid #ee4d2d;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 5px 5px 0;
    }
    .rating-badge {
        display: inline-block;
        background-color: #ffc107;
        color: #000;
        padding: 0.25rem 0.5rem;
        border-radius: 3px;
        font-weight: bold;
        margin-right: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# 标题
st.markdown('<h1 class="main-header">🛍️ Shopee评论爬取分析工具</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">高效提取、分析Shopee商品评论数据</p>', unsafe_allow_html=True)

class ShopeeReviewScraper:
    """Shopee评论爬取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://shopee.co.id/',
        })
    
    def extract_ids_from_url(self, url: str) -> tuple:
        """从URL提取商品ID和店铺ID"""
        try:
            # 方法1：从URL模式提取
            patterns = [
                r'i\.(\d+)\.(\d+)',  # 标准Shopee URL模式
                r'item/(\d+)/(\d+)',  # 另一种模式
                r'shopid=(\d+)&itemid=(\d+)',  # 参数模式
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    shop_id, item_id = match.groups()
                    return shop_id, item_id
            
            # 方法2：尝试从HTML页面提取（如果提供了完整URL）
            if url.startswith('http'):
                response = self.session.get(url, timeout=10)
                # 查找商品ID和店铺ID
                html = response.text
                shop_id_match = re.search(r'"shopid"\s*:\s*(\d+)', html)
                item_id_match = re.search(r'"itemid"\s*:\s*(\d+)', html)
                
                if shop_id_match and item_id_match:
                    return shop_id_match.group(1), item_id_match.group(1)
            
            return None, None
            
        except Exception as e:
            st.warning(f"URL解析失败: {str(e)}")
            return None, None
    
    def fetch_reviews_api(self, shop_id: str, item_id: str, limit: int = 100) -> List[Dict]:
        """通过API获取评论数据"""
        all_reviews = []
        
        try:
            # Shopee评论API（印尼站）
            base_url = "https://shopee.co.id/api/v2/item/get_ratings"
            
            offset = 0
            batch_size = 20  # 每页20条
            
            with st.spinner("正在爬取评论数据..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                while offset < limit:
                    params = {
                        'itemid': item_id,
                        'shopid': shop_id,
                        'offset': offset,
                        'limit': batch_size,
                        'type': 0,  # 所有评论
                        'filter': 0,  # 所有类型
                        'flag': 1
                    }
                    
                    try:
                        response = self.session.get(base_url, params=params, timeout=15)
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            if data.get('error'):
                                st.error(f"API错误: {data.get('error', '未知错误')}")
                                break
                            
                            ratings = data.get('data', {}).get('ratings', [])
                            
                            if not ratings:
                                break  # 没有更多数据
                            
                            for rating in ratings:
                                review = self.parse_review(rating)
                                if review:
                                    all_reviews.append(review)
                            
                            # 更新进度
                            progress = min(100, int((offset / limit) * 100))
                            progress_bar.progress(progress)
                            status_text.text(f"已获取 {len(all_reviews)} 条评论...")
                            
                            offset += batch_size
                            
                            # 延迟避免被封
                            time.sleep(0.5)
                            
                        else:
                            st.warning(f"请求失败: HTTP {response.status_code}")
                            break
                            
                    except Exception as e:
                        st.error(f"请求出错: {str(e)}")
                        break
                
                progress_bar.progress(100)
                status_text.text(f"完成！共获取 {len(all_reviews)} 条评论")
                
        except Exception as e:
            st.error(f"爬取过程出错: {str(e)}")
        
        return all_reviews
    
    def fetch_reviews_selenium(self, url: str, max_reviews: int = 100) -> List[Dict]:
        """使用Selenium模拟浏览器获取评论（备用方法）"""
        try:
            # 这里需要安装selenium和webdriver
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            
            st.info("正在启动浏览器模拟...")
            
            # 设置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            driver.get(url)
            time.sleep(3)
            
            reviews = []
            
            # 这里需要根据实际页面结构调整选择器
            # 由于页面结构可能变化，这只是一个示例
            try:
                review_elements = driver.find_elements(By.CSS_SELECTOR, 'div[class*="product-review"]')
                
                for element in review_elements[:max_reviews]:
                    try:
                        # 解析评论元素
                        review_data = self.parse_review_element(element)
                        if review_data:
                            reviews.append(review_data)
                    except:
                        continue
                        
            except Exception as e:
                st.warning(f"解析页面失败: {str(e)}")
            
            driver.quit()
            return reviews
            
        except ImportError:
            st.error("需要安装selenium: pip install selenium")
            return []
        except Exception as e:
            st.error(f"Selenium爬取失败: {str(e)}")
            return []
    
    def parse_review(self, rating_data: Dict) -> Optional[Dict]:
        """解析API返回的评论数据"""
        try:
            # 提取用户信息
            username = rating_data.get('author_username', '')
            if not username or username == 'null':
                username = rating_data.get('author_portrait', '').split('/')[-1].split('.')[0]
            
            # 处理匿名用户
            if not username or len(username) < 2:
                username = f"用户_{hash(rating_data.get('cmtid', '')) % 10000:04d}"
            
            # 评分
            rating = rating_data.get('rating_star', 0)
            
            # 评论内容
            comment = rating_data.get('comment', '')
            if not comment or comment == 'null':
                comment = rating_data.get('detailed_rating', [{}])[0].get('comment', '') if rating_data.get('detailed_rating') else ''
            
            # 时间戳转换
            ctime = rating_data.get('ctime', 0)
            if ctime:
                try:
                    review_time = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M')
                except:
                    review_time = str(ctime)
            else:
                review_time = '未知时间'
            
            # 产品变体
            product_items = rating_data.get('product_items', [{}])
            variation = product_items[0].get('model_name', '') if product_items else ''
            
            # 卖家回复
            seller_response = ''
            if rating_data.get('seller_reply'):
                seller_response = rating_data['seller_reply'].get('comment', '')
            
            # 点赞数
            like_count = rating_data.get('like_count', 0)
            
            return {
                'username': username,
                'time': review_time,
                'rating': rating,
                'comment': comment,
                'variation': variation,
                'seller_response': seller_response,
                'like_count': like_count,
                'images_count': len(rating_data.get('images', [])),
                'source': 'api'
            }
            
        except Exception as e:
            st.warning(f"解析评论失败: {str(e)}")
            return None
    
    def parse_review_element(self, element) -> Optional[Dict]:
        """解析Selenium获取的评论元素"""
        try:
            # 这里需要根据实际页面结构调整
            # 由于页面结构可能变化，这只是一个示例解析逻辑
            text = element.text
            
            # 提取用户名（通常以*号隐藏部分字符）
            username_match = re.search(r'^([^*\n]+)', text)
            username = username_match.group(1).strip() if username_match else '匿名用户'
            
            # 提取评分（通过★符号数量）
            stars = text.count('★')
            rating = stars if 1 <= stars <= 5 else 5
            
            # 提取日期
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
            review_time = date_match.group(1) if date_match else '未知时间'
            
            # 提取评论内容（简化提取）
            lines = text.split('\n')
            comment_lines = []
            in_comment = False
            
            for line in lines:
                if line.strip() and not line.startswith(username) and not re.match(r'\d{4}-\d{2}-\d{2}', line):
                    if 'Variation:' not in line and 'Seller' not in line:
                        comment_lines.append(line.strip())
            
            comment = ' '.join(comment_lines[:3])  # 只取前3行
            
            return {
                'username': username,
                'time': review_time,
                'rating': rating,
                'comment': comment[:200],  # 限制长度
                'variation': '',
                'seller_response': '',
                'like_count': 0,
                'images_count': 0,
                'source': 'selenium'
            }
            
        except Exception as e:
            return None
    
    def analyze_reviews(self, reviews_df):
        """分析评论数据"""
        analysis = {}
        
        if reviews_df.empty:
            return analysis
        
        # 基本统计
        analysis['total_reviews'] = len(reviews_df)
        analysis['avg_rating'] = reviews_df['rating'].mean()
        
        # 评分分布
        rating_counts = reviews_df['rating'].value_counts().sort_index()
        analysis['rating_distribution'] = rating_counts
        
        # 时间分析（如果有时间数据）
        if 'time' in reviews_df.columns and pd.api.types.is_datetime64_any_dtype(reviews_df['time']):
            reviews_df['date'] = reviews_df['time'].dt.date
            daily_counts = reviews_df['date'].value_counts().sort_index()
            analysis['daily_trend'] = daily_counts
        
        # 评论长度分析
        reviews_df['comment_length'] = reviews_df['comment'].apply(len)
        analysis['avg_comment_length'] = reviews_df['comment_length'].mean()
        
        # 情感关键词（简单版）
        positive_words = ['bagus', 'baik', 'mantap', 'puas', 'recommended', 'suka', 'senang', 'glowing', 'cerah']
        negative_words = ['jelek', 'buruk', 'kecewa', 'tidak', 'gagal', 'rusak', 'palsu']
        
        reviews_df['positive_score'] = reviews_df['comment'].apply(
            lambda x: sum(1 for word in positive_words if word.lower() in x.lower())
        )
        reviews_df['negative_score'] = reviews_df['comment'].apply(
            lambda x: sum(1 for word in negative_words if word.lower() in x.lower())
        )
        
        analysis['positive_count'] = (reviews_df['positive_score'] > 0).sum()
        analysis['negative_count'] = (reviews_df['negative_score'] > 0).sum()
        
        return analysis

def main():
    """主函数"""
    
    # 初始化爬虫
    scraper = ShopeeReviewScraper()
    
    # 侧边栏
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/Shopee.svg/320px-Shopee.svg.png", 
                 width=150, caption="Shopee Indonesia")
        
        st.markdown("### ⚙️ 配置选项")
        
        # 输入方式选择
        input_method = st.radio("输入方式", ["商品URL", "手动输入ID"])
        
        if input_method == "商品URL":
            product_url = st.text_input(
                "商品链接",
                placeholder="https://shopee.co.id/...",
                help="粘贴完整的Shopee商品链接"
            )
            shop_id, item_id = None, None
            
            if product_url:
                with st.spinner("正在解析URL..."):
                    shop_id, item_id = scraper.extract_ids_from_url(product_url)
                
                if shop_id and item_id:
                    st.success(f"解析成功！")
                    st.info(f"店铺ID: `{shop_id}`")
                    st.info(f"商品ID: `{item_id}`")
                else:
                    st.warning("无法从URL解析ID，请检查链接格式")
        else:
            shop_id = st.text_input("店铺ID", placeholder="如：809769142")
            item_id = st.text_input("商品ID", placeholder="如：42800295602")
        
        # 爬取设置
        st.markdown("### 📊 爬取设置")
        max_reviews = st.slider("最大评论数", 10, 1000, 100, 10)
        
        use_api = st.checkbox("使用API爬取（推荐）", value=True)
        use_selenium = st.checkbox("使用浏览器模拟（备用）", value=False)
        
        if use_selenium:
            st.warning("Selenium需要额外安装，速度较慢")
        
        st.markdown("### 💾 导出选项")
        export_format = st.multiselect(
            "导出格式",
            ["CSV", "Excel", "JSON"],
            default=["CSV"]
        )
        
        st.markdown("---")
        
        if st.button("🚀 开始爬取", type="primary", use_container_width=True):
            st.session_state.start_scraping = True
        else:
            st.session_state.start_scraping = False
    
    # 主界面
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📝 输入商品信息")
        
        # 如果未从侧边栏获取，在这里也可以输入
        if input_method == "商品URL" and not product_url:
            product_url = st.text_input("在这里输入商品链接：", key="main_url")
            if product_url:
                shop_id, item_id = scraper.extract_ids_from_url(product_url)
        
        if not shop_id or not item_id:
            st.info("请在侧边栏输入商品信息")
            
    with col2:
        st.markdown("### 📊 数据预览")
        if 'reviews_df' in st.session_state and not st.session_state.reviews_df.empty:
            df = st.session_state.reviews_df
            st.metric("总评论数", len(df))
            st.metric("平均评分", f"{df['rating'].mean():.1f} ⭐")
            st.metric("有图片的评论", f"{df[df['images_count'] > 0].shape[0]} 条")
    
    # 爬取按钮触发
    if st.session_state.get('start_scraping', False) and shop_id and item_id:
        st.markdown("---")
        st.markdown("### 🔍 正在爬取评论...")
        
        # 清空之前的缓存
        if 'reviews_df' in st.session_state:
            del st.session_state.reviews_df
        
        # 爬取评论
        reviews = []
        
        if use_api:
            reviews = scraper.fetch_reviews_api(shop_id, item_id, max_reviews)
        
        if use_selenium and len(reviews) < max_reviews:
            if product_url:
                selenium_reviews = scraper.fetch_reviews_selenium(product_url, max_reviews - len(reviews))
                reviews.extend(selenium_reviews)
        
        if reviews:
            # 转换为DataFrame
            reviews_df = pd.DataFrame(reviews)
            
            # 时间列转换
            if 'time' in reviews_df.columns:
                reviews_df['time'] = pd.to_datetime(reviews_df['time'], errors='coerce')
            
            # 保存到session
            st.session_state.reviews_df = reviews_df
            
            # 显示成功信息
            st.success(f"✅ 成功爬取 {len(reviews_df)} 条评论！")
            
            # 显示数据
            st.markdown("### 📋 评论数据表")
            st.dataframe(
                reviews_df[['username', 'time', 'rating', 'comment', 'like_count']].head(20),
                use_container_width=True,
                hide_index=True
            )
            
            # 数据分析
            st.markdown("### 📈 数据分析")
            
            # 评分分布图表
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = go.Figure(data=[
                    go.Pie(
                        labels=[f'{i}星' for i in range(1, 6)],
                        values=[(reviews_df['rating'] == i).sum() for i in range(1, 6)],
                        hole=.3,
                        marker_colors=['#ff6b6b', '#ffa726', '#ffd166', '#06d6a0', '#118ab2']
                    )
                ])
                fig1.update_layout(title_text="评分分布", height=300)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # 评论长度分布
                reviews_df['comment_length'] = reviews_df['comment'].apply(len)
                fig2 = px.histogram(
                    reviews_df, 
                    x='comment_length',
                    nbins=20,
                    title="评论长度分布",
                    labels={'comment_length': '评论字数'}
                )
                fig2.update_layout(height=300)
                st.plotly_chart(fig2, use_container_width=True)
            
            # 时间趋势（如果有时间数据）
            if 'time' in reviews_df.columns and not reviews_df['time'].isna().all():
                reviews_df['date'] = reviews_df['time'].dt.date
                daily_counts = reviews_df['date'].value_counts().sort_index()
                
                fig3 = px.line(
                    x=daily_counts.index,
                    y=daily_counts.values,
                    title="每日评论趋势",
                    labels={'x': '日期', 'y': '评论数'}
                )
                st.plotly_chart(fig3, use_container_width=True)
            
            # 导出功能
            st.markdown("### 💾 导出数据")
            
            col1, col2, col3 = st.columns(3)
            
            # CSV导出
            if "CSV" in export_format:
                with col1:
                    csv = reviews_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 下载CSV",
                        data=csv,
                        file_name=f"shopee_reviews_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        help="下载为CSV格式，可用Excel打开"
                    )
            
            # Excel导出
            if "Excel" in export_format:
                with col2:
                    # 使用BytesIO创建Excel文件
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        reviews_df.to_excel(writer, index=False, sheet_name='评论数据')
                        
                        # 添加汇总表
                        summary_df = pd.DataFrame({
                            '统计项': ['总评论数', '平均评分', '最长评论', '最短评论'],
                            '值': [
                                len(reviews_df),
                                f"{reviews_df['rating'].mean():.2f}",
                                reviews_df['comment'].apply(len).max(),
                                reviews_df['comment'].apply(len).min()
                            ]
                        })
                        summary_df.to_excel(writer, index=False, sheet_name='数据汇总')
                    
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📊 下载Excel",
                        data=excel_data,
                        file_name=f"shopee_reviews_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="下载为Excel格式，包含数据汇总"
                    )
            
            # JSON导出
            if "JSON" in export_format:
                with col3:
                    json_str = reviews_df.to_json(orient='records', force_ascii=False, indent=2)
                    st.download_button(
                        label="📄 下载JSON",
                        data=json_str,
                        file_name=f"shopee_reviews_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        help="下载为JSON格式，便于程序处理"
                    )
            
            # 显示原始数据选项
            with st.expander("查看原始数据"):
                st.json(reviews_df.head(10).to_dict(orient='records'))
                
        else:
            st.error("未能获取到评论数据，请尝试以下方法：")
            st.markdown("""
            1. 检查商品链接是否正确
            2. 尝试使用浏览器模拟模式
            3. 确保商品有评论
            4. 可能是Shopee反爬虫机制，请稍后重试
            """)
    
    # 如果没有数据，显示示例
    elif 'reviews_df' not in st.session_state:
        st.markdown("---")
        st.markdown("### 🎯 使用说明")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("#### 1️⃣ 输入商品信息")
            st.markdown("""
            - 粘贴商品完整链接
            - 或手动输入店铺ID和商品ID
            """)
        
        with col2:
            st.markdown("#### 2️⃣ 配置爬取选项")
            st.markdown("""
            - 设置最大评论数
            - 选择爬取方法
            - 选择导出格式
            """)
        
        with col3:
            st.markdown("#### 3️⃣ 开始爬取分析")
            st.markdown("""
            - 点击开始爬取
            - 查看数据分析
            - 导出所需格式
            """)
        
        # 示例数据
        st.markdown("### 📊 示例数据预览")
        example_data = pd.DataFrame({
            'username': ['用户_1234', '用户_5678', '用户_9101'],
            'time': ['2025-01-15', '2025-01-14', '2025-01-13'],
            'rating': [5, 4, 3],
            'comment': ['产品质量很好，很喜欢！', '发货速度有点慢，但产品不错', '一般般，没有想象中好'],
            'like_count': [10, 5, 2]
        })
        st.dataframe(example_data, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
