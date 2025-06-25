from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def join_key(prefix, suffix):
    """템플릿에서 문자열 키 조합 시 사용: '재무상태표_' + '2024' → '재무상태표_2024'"""
    return f"{prefix}{suffix}"

@register.filter
def is_not_in(value, arg_str):
    try:
        exclude_list = [x.strip() for x in arg_str.split(',')]
        return value not in exclude_list
    except:
        return True  # 오류 시 기본적으로 "not in"으로 처리

@register.filter
def display_value(val):
    """None이면 --로 출력"""
    return "--" if val is None else val
