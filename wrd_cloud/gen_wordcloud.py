import re
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import string
from sklearn.feature_extraction.text import TfidfVectorizer

# 下载NLTK数据
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

def normalize_special_terms(text):
    """保护特殊术语不被小写化，并统一复数形式"""
    # 定义需要保护的特殊术语（保持原样）
    special_terms = {
        'genai': 'GenAI',
        'llm': 'LLM', 
        'llms': 'LLM',
        'ai': 'AI',
        'nlp': 'NLP',
        'hrc': 'HRC',
        'hac': 'HAC',
        'iot': 'IoT',
        'dt': 'DT',
        'xr': 'XR',
        'vr': 'VR',
        'ar': 'AR',
        'chatgpt': 'ChatGPT'
    }
    
    # 定义复数统一规则
    plural_unification = {
        'systems': 'system',
        'models': 'model', 
        'agents': 'agent',
        'methods': 'method',
        'approaches': 'approach',
        'frameworks': 'framework',
        'techniques': 'technique',
        'algorithms': 'algorithm',
        'applications': 'application',
        'solutions': 'solution',
        'processes': 'process',
        'tasks': 'task',
        'problems': 'problem',
        'challenges': 'challenge',
        'capabilities': 'capability',
        'technologies': 'technology',
        'strategies': 'strategy'
    }
    
    # 先处理复数统一
    for plural, singular in plural_unification.items():
        text = re.sub(r'\b' + plural + r'\b', singular, text, flags=re.IGNORECASE)
    
    # 然后保护特殊术语
    for lowercase, proper in special_terms.items():
        text = re.sub(r'\b' + lowercase + r'\b', proper, text, flags=re.IGNORECASE)
    
    return text


def extract_abstracts_from_ris(ris_content):
    """从RIS格式文件中提取摘要"""
    abstracts = []
    lines = ris_content.split('\n')
    
    current_record = {}
    for line in lines:
        line = line.rstrip()
        
        # 识别字段
        if line.startswith('AB  - '):
            # 提取摘要内容
            abstract = line[6:].strip()
            if abstract and len(abstract) > 20:
                current_record['abstract'] = abstract
        elif line.startswith('ER  - '):
            # 记录结束
            if 'abstract' in current_record:
                abstracts.append(current_record['abstract'])
            current_record = {}
        elif line.startswith('TY  - '):
            # 新记录开始，清除前一条记录
            if current_record and 'abstract' in current_record:
                abstracts.append(current_record['abstract'])
            current_record = {}
    
    # 处理最后一条记录
    if current_record and 'abstract' in current_record:
        abstracts.append(current_record['abstract'])
    
    return abstracts


def generate_word_cloud(abstracts, output_file='llm_research_wordcloud.png'):
    """使用TF-IDF生成词云图"""

    processed_abstracts = []
    for abstract in abstracts:
        abstract = abstract.lower()
        abstract = normalize_special_terms(abstract)
        processed_abstracts.append(abstract)
    
    # 定义自定义停用词
    custom_stopwords = {'based', 'using', 'however', 'within', 'also', 'case', 'use', 'used'}
    # 合并英文停用词和自定义停用词
    stop_words_list = list(set(stopwords.words('english')).union(custom_stopwords))
    
    # 使用TfidfVectorizer计算TF-IDF权重
    tfidf_vectorizer = TfidfVectorizer(
        max_features=1000,
        stop_words=stop_words_list,  # 使用合并后的停用词列表
        lowercase=True,
        max_df=0.9,
        min_df=1,  # 降低 min_df 确保关键词不被过滤
        ngram_range=(1, 1)
    )
    
    # 拟合并转换文本
    tfidf_matrix = tfidf_vectorizer.fit_transform(processed_abstracts)
    
    # 获取词汇表和TF-IDF分数
    feature_names = tfidf_vectorizer.get_feature_names_out()
    
    # 计算每个词的平均TF-IDF分数
    tfidf_scores = tfidf_matrix.mean(axis=0).A1
    
    # 创建词频字典（使用TF-IDF分数）
    word_freq = dict(zip(feature_names, tfidf_scores))
    
    # 过滤权重太小的词，但保留关键词
    word_freq = {
        word: score for word, score in word_freq.items() 
        if score > 0.0005 
    }
    
    # 标准化权重到0-1范围以便词云显示
    max_score = max(word_freq.values()) if word_freq else 1
    word_freq = {word: score / max_score for word, score in word_freq.items()}
    
    # 生成词云
    wordcloud = WordCloud(
        width=1200,
        height=800,
        background_color='white',
        colormap='plasma',
        max_words=100,
        relative_scaling=0.5,
        collocations=False
    ).generate_from_frequencies(word_freq)
    
    # 绘制词云
    plt.figure(figsize=(15, 10))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    # plt.title('Word Cloud: LLM and Human Collaboration Research (TF-IDF)', 
    #           fontsize=18, pad=20, weight='bold')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.show()
    
    return word_freq


def main():
    # 读取RIS文件
    ris_file_path = '../search_result/ris/refined/qury_res_unique_with_abstracts.ris'
    
    try:
        with open(ris_file_path, 'r', encoding='utf-8') as file:
            ris_content = file.read()
    except FileNotFoundError:
        print(f"错误: 找不到文件 {ris_file_path}")
        print("请确保RIS文件路径正确")
        return
    
    print("正在从RIS文件中提取摘要...")
    
    # 提取摘要
    all_abstracts = extract_abstracts_from_ris(ris_content)
    
    print(f"\n找到 {len(all_abstracts)} 个摘要")
    
    if all_abstracts:
        # 生成词云和分析（使用TF-IDF）
        word_freq = generate_word_cloud(all_abstracts)
        
        # 保存处理后的文本
        with open('processed_abstracts.txt', 'w', encoding='utf-8') as f:
            for i, abstract in enumerate(all_abstracts, 1):
                f.write(f"摘要 {i}:\n{abstract}\n{'-'*50}\n")
        
        print(f"\n分析完成！")
        print(f"   词云图已保存为: llm_research_wordcloud.png")
        print(f"   处理后的摘要已保存为: processed_abstracts.txt")
    else:
        print("未找到任何摘要，请检查RIS文件格式")

if __name__ == "__main__":
    main()