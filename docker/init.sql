CREATE DATABASE IF NOT EXISTS mrag;
USE mrag;

CREATE TABLE IF NOT EXISTS `t_user` (
  `oid` bigint unsigned NOT NULL,
  `user_identifier` varchar(100) COLLATE utf8mb4_bin NOT NULL COMMENT '用户标识(邮箱或手机号)',
  `cstatus` tinyint DEFAULT '0' COMMENT '状态:1-删除',
  `crt` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `upt` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='简单用户表';

CREATE TABLE IF NOT EXISTS `t_document` (
  `oid` bigint unsigned NOT NULL,
  `doc_name` varchar(255) COLLATE utf8mb4_bin NOT NULL COMMENT '文档名称',
  `doc_size` bigint unsigned NOT NULL COMMENT '文档大小',
  `file_path` varchar(200) COLLATE utf8mb4_bin NOT NULL COMMENT 'MinIO存储路径',
  `file_hash` varchar(64) COLLATE utf8mb4_bin NOT NULL COMMENT '文件MD5',
  `mime_type` varchar(64) COLLATE utf8mb4_bin NOT NULL COMMENT '文件类型',
  `chunk_count` int DEFAULT '0' COMMENT '分片数量',
  `chunk_status` tinyint DEFAULT '0' COMMENT '分片状态:0-未分片,1-分片中,2-已完成',
  `upload_user_oid` bigint unsigned NOT NULL COMMENT '上传用户标识',
  `crt` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `upt` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='文档信息表';

CREATE TABLE IF NOT EXISTS `t_document_chunk` (
  `oid` bigint unsigned NOT NULL,
  `doc_oid` bigint NOT NULL COMMENT '文档ID',
  `chunk_index` int NOT NULL COMMENT '分片序号',
  `chunk_content` text COLLATE utf8mb4_bin NOT NULL COMMENT '分片内容',
  `content_hash` varchar(64) COLLATE utf8mb4_bin NOT NULL COMMENT '内容MD5',
  `chunk_size` int NOT NULL COMMENT '分片大小',
  `vector_id` varchar(100) COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Elasticsearch向量ID',
  `crt` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `upt` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`oid`) COMMENT '文档分片表'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='文档分片表';