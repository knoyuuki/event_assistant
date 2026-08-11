-- ============================================================
-- 迁移 002: 新增用户表（登录鉴权 / 分权分域）
--
-- 日期    : 2026-08-11
-- 背景    : 新增登录模块（PBKDF2 密码哈希、会话存 Redis、失败锁定），
--           角色 admin=管理（增删改） / user=浏览+会议排序
-- 幂等性  : CREATE TABLE IF NOT EXISTS，可重复执行
-- ============================================================

CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE COMMENT '登录名',
    `password_hash` VARCHAR(255) NOT NULL COMMENT 'PBKDF2-HMAC-SHA256 哈希',
    `role` VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT 'admin/user',
    `display_name` VARCHAR(100) DEFAULT NULL COMMENT '显示名',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '1=启用 0=禁用',
    `last_login_at` DATETIME DEFAULT NULL COMMENT '最近登录时间',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户';

-- 首次启动时若表为空，后端会自动创建初始管理员 admin（密码见 config/admin_initial_password.txt）
