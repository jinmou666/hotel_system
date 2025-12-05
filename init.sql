-- 数据库初始化脚本 (MySQL 8.0+)
-- 警告：请勿擅自修改字段名，否则全组代码无法合并！

CREATE DATABASE IF NOT EXISTS hotel_ac_system DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hotel_ac_system;

-- 1. 客户表 (Customer)
CREATE TABLE IF NOT EXISTS `customer` (
    `customer_id` VARCHAR(32) NOT NULL COMMENT '客户唯一标识',
    `name` VARCHAR(50) NOT NULL COMMENT '姓名',
    `id_number` VARCHAR(18) NOT NULL COMMENT '身份证号',
    `phone` VARCHAR(11) DEFAULT NULL COMMENT '联系电话',
    `registration_date` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    PRIMARY KEY (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 房间表 (Room)
-- 预置 5 个房间，完全对应老师 Excel 中的 R1-R5 参数
CREATE TABLE IF NOT EXISTS `room` (
    `room_id` VARCHAR(10) NOT NULL COMMENT '房间号 (101-105)',
    `current_temp` DECIMAL(5,2) DEFAULT 25.00 COMMENT '当前室温',
    `target_temp` DECIMAL(5,2) DEFAULT 25.00 COMMENT '目标温度',
    `fan_speed` VARCHAR(10) DEFAULT 'MEDIUM' COMMENT '风速: LOW, MEDIUM, HIGH',
    `power_status` VARCHAR(5) DEFAULT 'OFF' COMMENT '开关状态: ON, OFF',
    `fee_rate` DECIMAL(5,2) DEFAULT 1.00 COMMENT '当前费率',
    `current_fee` DECIMAL(10,2) DEFAULT 0.00 COMMENT '当前累计费用',
    `total_fee` DECIMAL(10,2) DEFAULT 0.00 COMMENT '总费用(含历史)',
    `customer_id` VARCHAR(32) DEFAULT NULL COMMENT '当前入住客户ID，空闲为NULL',
    `status` VARCHAR(20) DEFAULT 'AVAILABLE' COMMENT '房间状态: AVAILABLE, OCCUPIED',
    PRIMARY KEY (`room_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 初始化 5 个房间数据 (默认制冷模式初始温度，严格对齐 Excel 参数配置表)
INSERT INTO `room` (`room_id`, `current_temp`, `target_temp`) VALUES
('101', 32.0, 25.0),
('102', 28.0, 25.0),
('103', 30.0, 25.0),
('104', 29.0, 25.0),
('105', 35.0, 25.0)
ON DUPLICATE KEY UPDATE `current_temp` = VALUES(`current_temp`);

-- 3. 空调详单/流水表 (DetailRecord)
CREATE TABLE IF NOT EXISTS `detail_record` (
    `record_id` INT AUTO_INCREMENT COMMENT '流水号',
    `room_id` VARCHAR(10) NOT NULL,
    `start_time` DATETIME NOT NULL COMMENT '服务开始时间',
    `end_time` DATETIME DEFAULT NULL COMMENT '服务结束时间',
    `duration` INT DEFAULT 0 COMMENT '服务时长(秒)',
    `fan_speed` VARCHAR(10) NOT NULL COMMENT '当时风速',
    `fee_rate` DECIMAL(5,2) NOT NULL COMMENT '当时费率',
    `fee` DECIMAL(10,2) DEFAULT 0.00 COMMENT '该条记录费用',
    PRIMARY KEY (`record_id`),
    INDEX `idx_room_time` (`room_id`, `start_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 账单/发票表 (Invoice)
CREATE TABLE IF NOT EXISTS `invoice` (
    `invoice_id` VARCHAR(32) NOT NULL COMMENT '账单号',
    `room_id` VARCHAR(10) NOT NULL,
    `customer_id` VARCHAR(32) NOT NULL,
    `check_in_date` DATETIME NOT NULL COMMENT '入住时间',
    `check_out_date` DATETIME NOT NULL COMMENT '退房时间',
    `accommodation_fee` DECIMAL(10,2) DEFAULT 0.00 COMMENT '住宿费',
    `ac_fee` DECIMAL(10,2) DEFAULT 0.00 COMMENT '空调总费',
    `total_amount` DECIMAL(10,2) DEFAULT 0.00 COMMENT '总金额',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`invoice_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;