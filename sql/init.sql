-- ============================================================
-- 会务助手 — 数据库初始化脚本（表结构）
--
-- 适用版本: MySQL 8.0+
-- 库名    : event_assistant
-- 说明    : 全新部署时执行本文件即可获得当前完整表结构；
--           后续表结构变动请见 sql/migrations/ 目录（递增编号）。
-- 幂等性  : 各表均使用 IF NOT EXISTS，可重复执行。
-- ============================================================

CREATE DATABASE IF NOT EXISTS event_assistant
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE event_assistant;


CREATE TABLE IF NOT EXISTS `api_apps` (
    `id` int NOT NULL AUTO_INCREMENT,
    `app_id` varchar(64) NOT NULL COMMENT '外部应用标识',
    `app_name` varchar(100) NOT NULL COMMENT '应用名称',
    `secret_encrypted` text NOT NULL COMMENT 'Fernet 加密后的密钥',
    `status` tinyint NOT NULL DEFAULT '1' COMMENT '1=启用 0=禁用',
    `description` varchar(255) DEFAULT NULL COMMENT '备注',
    `expires_at` datetime DEFAULT NULL COMMENT '过期时间，NULL=永不过期',
    `last_called_at` datetime DEFAULT NULL COMMENT '最近调用时间',
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `app_id` (`app_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `api_call_logs` (
    `id` bigint NOT NULL AUTO_INCREMENT,
    `app_id` varchar(64) NOT NULL COMMENT '应用标识',
    `caller_ip` varchar(45) NOT NULL COMMENT '调用方IP',
    `method` varchar(10) NOT NULL COMMENT 'HTTP方法',
    `path` varchar(255) NOT NULL COMMENT '接口路径',
    `status_code` int NOT NULL COMMENT '状态码',
    `request_params` text COMMENT '请求参数(JSON)',
    `response_result` mediumtext COMMENT '返回结果(JSON)',
    `duration_ms` int DEFAULT NULL COMMENT '耗时(毫秒)',
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_log_app_created` (`app_id`,`created_at`),
    KEY `idx_log_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `departments` (
    `id` int NOT NULL AUTO_INCREMENT,
    `name` varchar(100) NOT NULL,
    `description` varchar(255) DEFAULT NULL,
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `category_id` int DEFAULT NULL COMMENT '所属分类ID',
    `sort_order` int NOT NULL DEFAULT '0' COMMENT '排序',
    PRIMARY KEY (`id`),
    UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `dept_categories` (
    `id` int NOT NULL AUTO_INCREMENT,
    `name` varchar(100) NOT NULL,
    `sort_order` int NOT NULL DEFAULT '0',
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `dept_sort_snapshots` (
    `id` int NOT NULL AUTO_INCREMENT,
    `name` varchar(200) NOT NULL COMMENT '存档名称',
    `note` text COMMENT '备注',
    `data` text NOT NULL COMMENT '排序数据JSON',
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `meetings` (
    `id` int NOT NULL AUTO_INCREMENT,
    `name` varchar(200) NOT NULL,
    `input_persons` text COMMENT '原始人员名单输入',
    `input_departments` text NOT NULL COMMENT '原始部门名单输入',
    `sorted_persons` text COMMENT '排序后人员名单JSON',
    `sorted_departments` text COMMENT '排序后部门名单JSON',
    `sort_snapshot_id` int DEFAULT NULL COMMENT '使用的部门排序存档ID',
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `persons` (
    `id` int NOT NULL AUTO_INCREMENT,
    `name` varchar(50) NOT NULL,
    `department` varchar(100) NOT NULL,
    `position` varchar(100) NOT NULL,
    `filename` varchar(255) NOT NULL,
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `position_title` varchar(100) DEFAULT NULL COMMENT '人员职位',
    `position_level` decimal(2,1) DEFAULT NULL COMMENT '职位等级',
    `managed_departments` text COMMENT '分管部门(JSON数组)',
    `managed_businesses` text COMMENT '分管业务(JSON数组)',
    `notes` text COMMENT '备注',
    `person_type` varchar(20) DEFAULT NULL COMMENT '人员类型：部门领导/员工/P1/P2',
    `sort_order` int DEFAULT NULL COMMENT '同部门同类型内排序',
    `phone` varchar(60) DEFAULT NULL COMMENT '手机号',
    `email` varchar(100) DEFAULT NULL COMMENT '邮箱',
    PRIMARY KEY (`id`),
    UNIQUE KEY `filename` (`filename`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `test_results` (
    `id` int NOT NULL AUTO_INCREMENT,
    `total` int NOT NULL,
    `correct` int NOT NULL,
    `score` decimal(5,2) NOT NULL,
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
