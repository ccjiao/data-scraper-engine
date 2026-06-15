"""
彩票数据解析器
将体彩API原始JSON转换为带号码拆分的统一格式
"""

from engine.config import DataSourceConfig


class LotteryParser:
    """彩票数据解析器"""

    def __init__(self, config: DataSourceConfig):
        self.config = config
        lottery_cfg = getattr(config, "_raw", {}).get("lottery", {})
        self.front_count = lottery_cfg.get("front_count", 5)
        self.back_count = lottery_cfg.get("back_count", 0)
        self.separator = lottery_cfg.get("separator", " ")

    def parse(self, record: dict) -> dict:
        """解析单条彩票记录"""
        result = dict(record)

        # 拆分号码
        draw_result = record.get("lotteryDrawResult", "")
        if draw_result:
            numbers = draw_result.split()
            front = numbers[:self.front_count] if len(numbers) >= self.front_count else numbers
            back = numbers[self.front_count:self.front_count + self.back_count] if self.back_count > 0 else []

            result["front_numbers"] = self.separator.join(front)
            result["back_numbers"] = self.separator.join(back) if back else ""

        # 解析奖级信息
        prize_list = record.get("prizeLevelList", [])
        self._parse_prizes(result, prize_list)

        # 清理原始字段
        for key in ["lotteryDrawResult", "prizeLevelList"]:
            if key in result:
                del result[key]

        return result

    def _parse_prizes(self, result: dict, prize_list: list):
        """解析奖级列表"""
        for prize in prize_list:
            level_name = prize.get("prizeLevelName", "")

            count_key = None
            amount_key = None

            if "一等奖" in level_name and "追加" not in level_name:
                count_key = "first_prize_count"
                amount_key = "first_prize_amount"
            elif "一等奖" in level_name and "追加" in level_name:
                count_key = "first_prize_extra_count"
                amount_key = "first_prize_extra_amount"
            elif "二等奖" in level_name and "追加" not in level_name:
                count_key = "second_prize_count"
                amount_key = "second_prize_amount"
            elif "二等奖" in level_name and "追加" in level_name:
                count_key = "second_prize_extra_count"
                amount_key = "second_prize_extra_amount"

            if count_key:
                result[count_key] = prize.get("stakeCount", 0)
            if amount_key:
                result[amount_key] = prize.get("stakeAmount", "0")

        # 默认值
        defaults = {
            "first_prize_count": 0, "first_prize_amount": "0",
            "first_prize_extra_count": 0, "first_prize_extra_amount": "0",
            "second_prize_count": 0, "second_prize_amount": "0",
            "second_prize_extra_count": 0, "second_prize_extra_amount": "0",
        }
        for k, v in defaults.items():
            result.setdefault(k, v)
