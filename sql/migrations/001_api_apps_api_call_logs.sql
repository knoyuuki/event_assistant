-- ============================================================
-- 迁移 001: 新增外部应用密钥管理与调用日志表
--
-- 日期    : 2026-08-11
-- 背景    : 新增外部接口签名加密规范与密钥管理模块
--           （/ext/* 签名接口、/api/app-keys 管理接口）
-- 幂等性  : CREATE TABLE IF NOT EXISTS，可重复执行
-- ============================================================

-- 外部应用（密钥 Fernet 加密存储，明文仅创建/轮换时展示一次）
CREATE TABLE IF NOT EXISTS `api_apps` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `app_id` VARCHAR(64) NOT NULL UNIQUE COMMENT '外部应用标识',
    `app_name` VARCHAR(100) NOT NULL COMMENT '应用名称',
    `secret_encrypted` TEXT NOT NULL COMMENT 'Fernet 加密后的密钥',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '1=启用 0=禁用',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '备注',
    `expires_at` DATETIME DEFAULT NULL COMMENT '过期时间，NULL=永不过期',
    `last_called_at` DATETIME DEFAULT NULL COMMENT '最近调用时间',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='外部应用密钥';

-- 外部接口调用日志（保留 7 天，后端定时清理）
CREATE TABLE IF NOT EXISTS `api_call_logs` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `app_id` VARCHAR(64) NOT NULL COMMENT '应用标识',
    `caller_ip` VARCHAR(45) NOT NULL COMMENT '调用方IP',
    `method` VARCHAR(10) NOT NULL COMMENT 'HTTP方法',
    `path` VARCHAR(255) NOT NULL COMMENT '接口路径',
    `status_code` INT NOT NULL COMMENT '状态码',
    `request_params` TEXT COMMENT '请求参数(JSON)',
    `response_result` MEDIUMTEXT COMMENT '返回结果(JSON)',
    `duration_ms` INT DEFAULT NULL COMMENT '耗时(毫秒)',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_log_app_created` (`app_id`, `created_at`),
    KEY `idx_log_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='外部接口调用日志';
