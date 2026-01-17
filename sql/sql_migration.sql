CREATE SCHEMA IF NOT EXISTS FLYTAU ;

USE FLYTAU;

CREATE TABLE FLIGHT_ATTENDANT (
ID_A VARCHAR(45) NOT NULL UNIQUE,
H_FIRST_NAME VARCHAR(45),
H_LAST_NAME VARCHAR(45),
PHONE_NUM VARCHAR(45),
CITY VARCHAR(45),
STREET VARCHAR(45),
HOUSE_NUM INT,
START_DATE DATE,
IS_QUALIFIED BOOLEAN,
PRIMARY KEY (ID_A)
);

CREATE TABLE PILOT (
ID_P VARCHAR(45) NOT NULL UNIQUE,
H_FIRST_NAME VARCHAR(45),
H_LAST_NAME VARCHAR(45),
PHONE_NUM VARCHAR(45),
CITY VARCHAR(45),
STREET VARCHAR(45),
HOUSE_NUM INT,
START_DATE DATE,
IS_QUALIFIED BOOLEAN,
PRIMARY KEY(ID_P)
);

CREATE TABLE MANAGER (
ID_M VARCHAR(45) NOT NULL UNIQUE,
H_FIRST_NAME VARCHAR(45),
H_LAST_NAME VARCHAR(45),
PHONE_NUM VARCHAR(45),
CITY VARCHAR(45),
STREET VARCHAR(45),
HOUSE_NUM INT,
START_DATE DATE,
M_PASSWORD VARCHAR(45),
PRIMARY KEY (ID_M)
);

CREATE TABLE GUEST (
G_MAIL VARCHAR(45) NOT NULL UNIQUE,
E_FIRST_NAME VARCHAR(45),
E_LAST_NAME VARCHAR(45),
PRIMARY KEY (G_MAIL)
);

CREATE TABLE REGISTER (
R_MAIL VARCHAR(45) NOT NULL UNIQUE,
R_PASSWORD VARCHAR(45),
BIRTH_DATE DATE,
PASSPORT_NUM VARCHAR(45),
REGITER_DATE DATE,
E_FIRST_NAME VARCHAR(45),
E_LAST_NAME VARCHAR(45),
PRIMARY KEY (R_MAIL)
);

CREATE TABLE GUEST_PHONE (
  G_MAIL VARCHAR(45) NOT NULL,
  PHONE_NUM VARCHAR(45) NOT NULL,
  PRIMARY KEY (G_MAIL, PHONE_NUM),
  FOREIGN KEY (G_MAIL) REFERENCES GUEST(G_MAIL)
);

CREATE TABLE REGISTER_PHONE (
  R_MAIL VARCHAR(45) NOT NULL,
  PHONE_NUM VARCHAR(45) NOT NULL,
  PRIMARY KEY (R_MAIL, PHONE_NUM),
  FOREIGN KEY (R_MAIL) REFERENCES REGISTER(R_MAIL)
);

CREATE TABLE AIRCRAFT (
AIRCRAFT_ID VARCHAR(45) NOT NULL UNIQUE,
SIZE ENUM("BIG","SMALL"),
MANUFACTURER VARCHAR(45),
PURCHASE_DATE DATE,
CAPACITY_BUSINESS INT,
CAPACITY_ECONOMY INT,
PRIMARY KEY (AIRCRAFT_ID)
);

CREATE TABLE ROUTE (
ROUTE_ID VARCHAR(45) NOT NULL UNIQUE,
DURATION TIME NOT NULL,
ORIGIN VARCHAR(45),
DESTINATION VARCHAR(45),
PRIMARY KEY (ROUTE_ID, DURATION)
);

CREATE TABLE FLIGHT (
FLIGHT_NUM VARCHAR(45) NOT NULL UNIQUE,
AIRCRAFT_ID VARCHAR(45) NOT NULL,
DURATION TIME NOT NULL,
ROUTE_ID VARCHAR(45) NOT NULL,
FLIGHT_STATUS ENUM('ACTIVE', 'FULL', 'COMPLETED', 'CANCELLED'),
DEPARTURE_DATE DATE,
DEPARTURE_TIME TIME,
ARRIVAL_DATE DATE,
ARRIVAL_TIME TIME,
ECONOMY_PRICE DECIMAL(10,2),
BUSINESS_PRICE DECIMAL(10,2),
PRIMARY KEY (FLIGHT_NUM),
FOREIGN KEY (AIRCRAFT_ID) REFERENCES AIRCRAFT(AIRCRAFT_ID),
FOREIGN KEY (ROUTE_ID, DURATION) REFERENCES ROUTE(ROUTE_ID, DURATION)
);

CREATE TABLE F_ORDER (
O_ID VARCHAR(45) NOT NULL UNIQUE,
FLIGHT_NUM VARCHAR(45) NOT NULL ,
G_MAIL VARCHAR(45) Null,
R_MAIL VARCHAR(45) Null,
O_STATUS ENUM('ACTIVE', 'COMPLETED', 'CUSTOMER_CANCELLED', 'SYSTEM_CANCELLED'),
O_DATE DATE,
ORDER_PRICE DECIMAL(10,2),
USER_TYPE ENUM("REGISTERD", "GUEST"),
CANACELATION_DATE_TIME DATETIME NULL,
PRIMARY KEY (O_ID),
FOREIGN KEY (FLIGHT_NUM) REFERENCES FLIGHT(FLIGHT_NUM),
FOREIGN KEY (G_MAIL) REFERENCES GUEST(G_MAIL),
FOREIGN KEY (R_MAIL) REFERENCES REGISTER(R_MAIL)
);
   
CREATE TABLE SEAT (
  AIRCRAFT_ID VARCHAR(45) NOT NULL,
  ROW_NUM INT NOT NULL,
  COL_LETTER CHAR(1) NOT NULL,
  CLASS ENUM('ECONOMY','BUSINESS') NOT NULL,
  PRIMARY KEY (AIRCRAFT_ID, ROW_NUM, COL_LETTER),
  FOREIGN KEY (AIRCRAFT_ID) REFERENCES AIRCRAFT(AIRCRAFT_ID)
);

CREATE TABLE ORDER_SEAT (
  O_ID VARCHAR(45) NOT NULL,
  AIRCRAFT_ID VARCHAR(45) NOT NULL,
  ROW_NUM INT NOT NULL,
  COL_LETTER CHAR(1) NOT NULL,
  PRIMARY KEY (O_ID, AIRCRAFT_ID, ROW_NUM, COL_LETTER),
  FOREIGN KEY (O_ID) REFERENCES F_ORDER(O_ID),
  FOREIGN KEY (AIRCRAFT_ID, ROW_NUM, COL_LETTER) REFERENCES SEAT(AIRCRAFT_ID, ROW_NUM, COL_LETTER)
);
 
CREATE TABLE ASSIGNED_PILOT (
ID_P VARCHAR(45) NOT NULL,
FLIGHT_NUM VARCHAR(45) NOT NULL,
PRIMARY KEY (ID_P, FLIGHT_NUM),
FOREIGN KEY (ID_P) REFERENCES PILOT(ID_P),
FOREIGN KEY (FLIGHT_NUM) REFERENCES FLIGHT(FLIGHT_NUM)
);


CREATE TABLE ASSIGHNED_ATTENDANT (
  ID_A VARCHAR(45) NOT NULL,
  FLIGHT_NUM VARCHAR(45) NOT NULL,
  PRIMARY KEY (ID_A, FLIGHT_NUM),
  FOREIGN KEY (ID_A) REFERENCES FLIGHT_ATTENDANT(ID_A),
  FOREIGN KEY (FLIGHT_NUM) REFERENCES FLIGHT(FLIGHT_NUM)
  );








---------------------------------------------------------------------------------------------------------------------------

USE FLYTAU;


-- ============================================================
-- 1) AIRCRAFT (חובה לפני FLIGHT!)
-- ============================================================
INSERT INTO AIRCRAFT (AIRCRAFT_ID, SIZE, MANUFACTURER, PURCHASE_DATE, CAPACITY_BUSINESS, CAPACITY_ECONOMY) VALUES
('AC001','SMALL','Boeing','2018-05-01',0,90),
('AC002','SMALL','Airbus','2019-07-15',0,110),
('AC003','SMALL','Dassault','2020-09-09',0,70),
('AC004','BIG','Boeing','2017-10-10',30,250),
('AC005','BIG','Airbus','2016-03-20',28,230),
('AC006','BIG','Dassault','2021-12-12',20,160);

-- =========================
-- REGISTER (3) + REGISTER_PHONE
-- =========================
INSERT INTO REGISTER (R_MAIL, R_PASSWORD, BIRTH_DATE, PASSPORT_NUM, REGITER_DATE, E_FIRST_NAME, E_LAST_NAME) VALUES
('roni@gmail.com','Roni1234','1999-04-12','P1234567','2025-07-01','Roni','Bar'),
('itay@gmail.com','Itay1234','2000-09-03','P2345678','2025-07-02','Itay','Levi'),
('maya@gmail.com','Maya1234','1998-01-25','P3456789','2025-07-03','Maya','Cohen');

INSERT INTO REGISTER_PHONE (R_MAIL, PHONE_NUM) VALUES
('roni@gmail.com','0509000001'),
('itay@gmail.com','0509000002'),
('maya@gmail.com','0509000003');

-- =========================
-- GUEST (3) + GUEST_PHONE
-- =========================
INSERT INTO GUEST (G_MAIL, E_FIRST_NAME, E_LAST_NAME) VALUES
('guest1@mail.com','Avi','Sason'),
('guest2@mail.com','Shir','Peretz'),
('guest3@mail.com','Tal','Green');

INSERT INTO GUEST_PHONE (G_MAIL, PHONE_NUM) VALUES
('guest1@mail.com','0508000001'),
('guest2@mail.com','0508000002'),
('guest3@mail.com','0508000003');
-- =========================
-- PILOT (10)  (IS_QUALIFIED = כשירות לטיסות ארוכות)
-- =========================
INSERT INTO PILOT (ID_P, H_FIRST_NAME, H_LAST_NAME, PHONE_NUM, CITY, STREET, HOUSE_NUM, START_DATE, IS_QUALIFIED) VALUES
('P001','אייל','כהן','050-7000001','Tel Aviv','Dizengoff',12,'2018-02-01',TRUE),
('P002','עמית','לוי','050-7000002','Ramat Gan','Bialik',8,'2019-05-10',TRUE),
('P003','גיל','בר','050-7000003','Jerusalem','King George',4,'2020-01-20',TRUE),
('P004','נועם','פרץ','050-7000004','Haifa','Hagana',15,'2017-09-12',TRUE),
('P005','יוסי','גרין','050-7000005','Netanya','Herzl',20,'2021-04-03',FALSE),
('P006','שני','אדלר','050-7000006','Ashdod','HaAtzmaut',6,'2016-11-25',TRUE),
('P007','ליאור','שלו','050-7000007','Tel Aviv','Rothschild',3,'2015-07-07',TRUE),
('P008','תומר','דיין','050-7000008','Beer Sheva','Rager',9,'2022-06-15',FALSE),
('P009','איתמר','כץ','050-7000009','Holon','Sokolov',11,'2019-12-30',TRUE),
('P010','הילה','מור','050-7000010','Petah Tikva','Haim Ozer',2,'2020-08-19',TRUE);


-- =========================
-- FLIGHT_ATTENDANT (20)  (IS_QUALIFIED = כשירות לטיסות ארוכות)
-- =========================
INSERT INTO FLIGHT_ATTENDANT (ID_A, H_FIRST_NAME, H_LAST_NAME, PHONE_NUM, CITY, STREET, HOUSE_NUM, START_DATE, IS_QUALIFIED) VALUES
('A001','נטע','לוי','050-6000001','Tel Aviv','Arlozorov',1,'2020-02-02',TRUE),
('A002','שקד','כהן','050-6000002','Tel Aviv','Ben Gurion',5,'2021-01-10',TRUE),
('A003','ליהי','בר','050-6000003','Haifa','Herzl',9,'2019-03-14',TRUE),
('A004','רותם','מור','050-6000004','Jerusalem','Jaffa',21,'2018-07-07',TRUE),
('A005','עדן','כץ','050-6000005','Rishon','Remez',6,'2022-05-01',FALSE),
('A006','מורן','פרץ','050-6000006','Holon','Sokolov',12,'2017-11-11',TRUE),
('A007','דנה','גרין','050-6000007','Netanya','Weizmann',3,'2016-08-20',TRUE),
('A008','שרון','אדלר','050-6000008','Ashdod','HaYam',17,'2023-02-09',FALSE),
('A009','טל','לוי','050-6000009','Beer Sheva','Rager',10,'2021-09-09',TRUE),
('A010','הדר','כהן','050-6000010','Tel Aviv','Dizengoff',44,'2019-12-12',TRUE),
('A011','נועה','בר','050-6000011','Haifa','Carmel',2,'2020-10-10',TRUE),
('A012','יערה','מור','050-6000012','Jerusalem','Emek Refaim',8,'2018-01-23',TRUE),
('A013','מאיה','כץ','050-6000013','Ramat Gan','Bialik',19,'2022-03-03',FALSE),
('A014','נוי','פרץ','050-6000014','Holon','Eilat',7,'2016-05-05',TRUE),
('A015','שירה','גרין','050-6000015','Netanya','Herzl',33,'2017-04-04',TRUE),
('A016','גל','אדלר','050-6000016','Ashdod','HaAtzmaut',14,'2019-06-06',FALSE),
('A017','רוני','שלו','050-6000017','Tel Aviv','Rothschild',6,'2020-09-01',TRUE),
('A018','יובל','דיין','050-6000018','Beer Sheva','Ben Zvi',1,'2021-02-15',TRUE),
('A019','עדי','כץ','050-6000019','Holon','Sokolov',30,'2023-07-07',TRUE),
('A020','לינה','מור','050-6000020','Haifa','Hagana',22,'2018-08-08',FALSE);


-- ============================================================
-- 2) ROUTE (existing + new)
-- ============================================================
INSERT INTO ROUTE (ROUTE_ID, DURATION, ORIGIN, DESTINATION) VALUES
('R001','01:10:00','TLV','LCA'),
('R002','02:20:00','TLV','ATH'),
('R003','05:45:00','TLV','LHR'),
('R004','06:00:00','TLV','MAD'),
('R005','06:30:00','TLV','DXB'),
('R006','08:15:00','TLV','JFK'),
('R007','04:30:00','TLV','CDG'),
('R008','03:55:00','TLV','FCO'),

('R009','03:40:00','TLV','AMS'),
('R010','02:55:00','TLV','VIE'),
('R011','03:10:00','TLV','BER'),
('R012','04:20:00','TLV','BCN'),
('R013','05:20:00','TLV','ZRH'),
('R014','02:10:00','TLV','SOF'),
('R015','01:55:00','TLV','IST'),
('R016','04:05:00','TLV','PRG'),
('R017','03:35:00','TLV','BUD'),
('R018','05:00:00','TLV','FRA'),

('R019','10:45:00','TLV','BKK'),
('R020','12:00:00','TLV','HND'),
('R021','07:20:00','TLV','YYZ'),
('R022','09:30:00','TLV','SFO'),
('R023','06:45:00','TLV','DEL'),
('R024','07:10:00','TLV','SIN');

-- ============================================================
-- 3) FLIGHT (עכשיו זה יעבוד כי AIRCRAFT קיימים)
-- ============================================================
INSERT INTO FLIGHT
(FLIGHT_NUM, AIRCRAFT_ID, DURATION, ROUTE_ID, FLIGHT_STATUS,
 DEPARTURE_DATE, DEPARTURE_TIME, ARRIVAL_DATE, ARRIVAL_TIME,
 ECONOMY_PRICE, BUSINESS_PRICE)
VALUES
('F400','AC001','01:10:00','R001','ACTIVE','2026-01-12','08:00:00','2026-01-12','09:10:00',360.00,0.00),
('F401','AC001','02:20:00','R002','ACTIVE','2026-01-18','10:00:00','2026-01-18','12:20:00',430.00,0.00),
('F402','AC002','03:55:00','R008','ACTIVE','2026-02-05','14:00:00','2026-02-05','17:55:00',740.00,0.00),
('F403','AC002','04:20:00','R012','COMPLETED','2025-12-02','07:30:00','2025-12-02','11:50:00',820.00,0.00),
('F404','AC003','05:20:00','R013','COMPLETED','2025-11-08','09:00:00','2025-11-08','14:20:00',880.00,0.00),
('F405','AC003','06:00:00','R004','CANCELLED','2026-03-02','06:00:00','2026-03-02','12:00:00',610.00,0.00),
('F406','AC001','03:10:00','R011','ACTIVE','2026-03-10','16:30:00','2026-03-10','19:40:00',690.00,0.00),
('F407','AC002','04:05:00','R016','ACTIVE','2026-04-01','12:15:00','2026-04-01','16:20:00',760.00,0.00),
('F408','AC003','02:55:00','R010','COMPLETED','2025-10-18','11:00:00','2025-10-18','13:55:00',520.00,0.00),

('F500','AC004','04:30:00','R007','ACTIVE','2026-01-15','11:45:00','2026-01-15','16:15:00',820.00,1950.00),
('F501','AC005','03:55:00','R008','ACTIVE','2026-01-28','09:10:00','2026-01-28','13:05:00',760.00,1800.00),
('F502','AC006','06:30:00','R005','ACTIVE','2026-02-12','13:00:00','2026-02-12','19:30:00',990.00,2500.00),
('F503','AC004','08:15:00','R006','COMPLETED','2025-12-20','14:15:00','2025-12-20','22:30:00',1250.00,3200.00),
('F504','AC005','10:45:00','R019','ACTIVE','2026-03-05','22:00:00','2026-03-06','08:45:00',2400.00,5200.00),
('F505','AC006','12:00:00','R020','COMPLETED','2025-11-25','23:30:00','2025-11-26','11:30:00',2700.00,5600.00),
('F506','AC004','06:45:00','R023','CANCELLED','2026-04-10','07:00:00','2026-04-10','13:45:00',1600.00,3800.00),
('F507','AC005','07:20:00','R021','ACTIVE','2026-02-20','10:00:00','2026-02-20','17:20:00',2100.00,4700.00),
('F508','AC006','09:30:00','R022','ACTIVE','2026-05-01','08:30:00','2026-05-01','18:00:00',2600.00,5400.00),
('F509','AC004','05:00:00','R018','COMPLETED','2025-09-12','06:10:00','2025-09-12','11:10:00',900.00,2200.00);

USE FLYTAU;

-- ============================================================
-- 4) SEATS  (NEW LOGIC: seats per row depends on Manufacturer+Size)
-- ============================================================



DROP TEMPORARY TABLE IF EXISTS nums;
CREATE TEMPORARY TABLE nums (n INT PRIMARY KEY);

INSERT INTO nums (n) VALUES
(1),(2),(3),(4),(5),(6),(7),(8),(9),(10),
(11),(12),(13),(14),(15),(16),(17),(18),(19),(20),
(21),(22),(23),(24),(25),(26),(27),(28),(29),(30),
(31),(32),(33),(34),(35),(36),(37),(38),(39),(40),
(41),(42),(43),(44),(45),(46),(47),(48),(49),(50),
(51),(52),(53),(54),(55),(56),(57),(58),(59),(60),
(61),(62),(63),(64),(65),(66),(67),(68),(69),(70),
(71),(72),(73),(74),(75),(76),(77),(78),(79),(80),
(81),(82),(83),(84),(85),(86),(87),(88),(89),(90),
(91),(92),(93),(94),(95),(96),(97),(98),(99),(100),
(101),(102),(103),(104),(105),(106),(107),(108),(109),(110),
(111),(112),(113),(114),(115),(116),(117),(118),(119),(120),
(121),(122),(123),(124),(125),(126),(127),(128),(129),(130),
(131),(132),(133),(134),(135),(136),(137),(138),(139),(140),
(141),(142),(143),(144),(145),(146),(147),(148),(149),(150),
(151),(152),(153),(154),(155),(156),(157),(158),(159),(160),
(161),(162),(163),(164),(165),(166),(167),(168),(169),(170),
(171),(172),(173),(174),(175),(176),(177),(178),(179),(180),
(181),(182),(183),(184),(185),(186),(187),(188),(189),(190),
(191),(192),(193),(194),(195),(196),(197),(198),(199),(200),
(201),(202),(203),(204),(205),(206),(207),(208),(209),(210),
(211),(212),(213),(214),(215),(216),(217),(218),(219),(220),
(221),(222),(223),(224),(225),(226),(227),(228),(229),(230),
(231),(232),(233),(234),(235),(236),(237),(238),(239),(240),
(241),(242),(243),(244),(245),(246),(247),(248),(249),(250),
(251),(252),(253),(254),(255),(256),(257),(258),(259),(260),
(261),(262),(263),(264),(265),(266),(267),(268),(269),(270),
(271),(272),(273),(274),(275),(276),(277),(278),(279),(280),
(281),(282),(283),(284),(285),(286),(287),(288),(289),(290),
(291),(292),(293),(294),(295),(296),(297),(298),(299),(300);

-- טבלת פריסה זמנית: כמה מושבים בשורה לכל (Manufacturer,Size)
DROP TEMPORARY TABLE IF EXISTS seat_rowsize;
CREATE TEMPORARY TABLE seat_rowsize (
  MANUFACTURER VARCHAR(45),
  SIZE VARCHAR(10),
  SEATS_PER_ROW INT,
  PRIMARY KEY (MANUFACTURER, SIZE)
);

INSERT INTO seat_rowsize (MANUFACTURER, SIZE, SEATS_PER_ROW) VALUES
('Boeing','SMALL',6),
('Boeing','BIG',10),
('Airbus','SMALL',6),
('Airbus','BIG',9),
('Dassault','SMALL',4),
('Dassault','BIG',6);


DROP TEMPORARY TABLE IF EXISTS seat_cols;
CREATE TEMPORARY TABLE seat_cols (
  MANUFACTURER VARCHAR(45),
  SIZE VARCHAR(10),
  COL_LETTER CHAR(1),
  PRIMARY KEY (MANUFACTURER, SIZE, COL_LETTER)
);

-- Boeing SMALL: A-F
INSERT INTO seat_cols VALUES
('Boeing','SMALL','A'),('Boeing','SMALL','B'),('Boeing','SMALL','C'),
('Boeing','SMALL','D'),('Boeing','SMALL','E'),('Boeing','SMALL','F');

-- Boeing BIG: A-J
INSERT INTO seat_cols VALUES
('Boeing','BIG','A'),('Boeing','BIG','B'),('Boeing','BIG','C'),('Boeing','BIG','D'),('Boeing','BIG','E'),
('Boeing','BIG','F'),('Boeing','BIG','G'),('Boeing','BIG','H'),('Boeing','BIG','I'),('Boeing','BIG','J');

-- Airbus SMALL: A-F
INSERT INTO seat_cols VALUES
('Airbus','SMALL','A'),('Airbus','SMALL','B'),('Airbus','SMALL','C'),
('Airbus','SMALL','D'),('Airbus','SMALL','E'),('Airbus','SMALL','F');

-- Airbus BIG: A-I
INSERT INTO seat_cols VALUES
('Airbus','BIG','A'),('Airbus','BIG','B'),('Airbus','BIG','C'),('Airbus','BIG','D'),('Airbus','BIG','E'),
('Airbus','BIG','F'),('Airbus','BIG','G'),('Airbus','BIG','H'),('Airbus','BIG','I');

-- Dassault SMALL: A-D
INSERT INTO seat_cols VALUES
('Dassault','SMALL','A'),('Dassault','SMALL','B'),('Dassault','SMALL','C'),('Dassault','SMALL','D');

-- Dassault BIG: A-F
INSERT INTO seat_cols VALUES
('Dassault','BIG','A'),('Dassault','BIG','B'),('Dassault','BIG','C'),
('Dassault','BIG','D'),('Dassault','BIG','E'),('Dassault','BIG','F');

-- -------------------------
-- BUSINESS seats
-- -------------------------
INSERT INTO SEAT (AIRCRAFT_ID, ROW_NUM, COL_LETTER, CLASS)
SELECT
  a.AIRCRAFT_ID,
  n.n AS ROW_NUM,
  sc.COL_LETTER,
  'BUSINESS' AS CLASS
FROM AIRCRAFT a
JOIN seat_rowsize sr
  ON sr.MANUFACTURER = a.MANUFACTURER AND sr.SIZE = a.SIZE
JOIN seat_cols sc
  ON sc.MANUFACTURER = a.MANUFACTURER AND sc.SIZE = a.SIZE
JOIN nums n
  ON n.n <= CEIL(IFNULL(a.CAPACITY_BUSINESS,0) / sr.SEATS_PER_ROW)
WHERE IFNULL(a.CAPACITY_BUSINESS,0) > 0;

-- -------------------------
-- ECONOMY seats
-- -------------------------
INSERT INTO SEAT (AIRCRAFT_ID, ROW_NUM, COL_LETTER, CLASS)
SELECT
  a.AIRCRAFT_ID,
  (CEIL(IFNULL(a.CAPACITY_BUSINESS,0) / sr.SEATS_PER_ROW) + n.n) AS ROW_NUM,
  sc.COL_LETTER,
  'ECONOMY' AS CLASS
FROM AIRCRAFT a
JOIN seat_rowsize sr
  ON sr.MANUFACTURER = a.MANUFACTURER AND sr.SIZE = a.SIZE
JOIN seat_cols sc
  ON sc.MANUFACTURER = a.MANUFACTURER AND sc.SIZE = a.SIZE
JOIN nums n
  ON n.n <= CEIL(IFNULL(a.CAPACITY_ECONOMY,0) / sr.SEATS_PER_ROW)
WHERE IFNULL(a.CAPACITY_ECONOMY,0) > 0;



USE FLYTAU;



-- ============================================================
-- 1) ASSIGNED_PILOT  (לפי הטיסות החדשות)
-- * SMALL flights => 2 pilots
-- * BIG flights   => 3 pilots
-- ============================================================

INSERT INTO ASSIGNED_PILOT (ID_P, FLIGHT_NUM) VALUES
-- SMALL (F400-F408) 2 pilots
('P001','F400'),('P005','F400'),
('P002','F401'),('P008','F401'),
('P003','F402'),('P009','F402'),
('P004','F403'),('P010','F403'),
('P006','F404'),('P005','F404'),
('P007','F405'),('P008','F405'),
('P001','F406'),('P002','F406'),
('P003','F407'),('P004','F407'),
('P006','F408'),('P009','F408'),

-- BIG (F500-F509) 3 pilots
('P001','F500'),('P002','F500'),('P003','F500'),
('P004','F501'),('P006','F501'),('P009','F501'),
('P001','F502'),('P007','F502'),('P009','F502'),
('P003','F503'),('P004','F503'),('P007','F503'),
('P001','F504'),('P002','F504'),('P006','F504'),
('P003','F505'),('P004','F505'),('P007','F505'),
('P006','F506'),('P007','F506'),('P009','F506'),
('P001','F507'),('P003','F507'),('P009','F507'),
('P002','F508'),('P004','F508'),('P007','F508'),
('P001','F509'),('P002','F509'),('P003','F509');

-- ============================================================
-- 2) ASSIGHNED_ATTENDANT (לפי הטיסות החדשות)
-- * SMALL flights => 3 attendants
-- * BIG flights   => 6 attendants
-- ============================================================

INSERT INTO ASSIGHNED_ATTENDANT (ID_A, FLIGHT_NUM) VALUES
-- SMALL (3 attendants each)
('A001','F400'),('A005','F400'),('A008','F400'),
('A002','F401'),('A013','F401'),('A016','F401'),
('A003','F402'),('A006','F402'),('A007','F402'),
('A004','F403'),('A010','F403'),('A020','F403'),
('A009','F404'),('A011','F404'),('A012','F404'),
('A014','F405'),('A015','F405'),('A017','F405'),
('A018','F406'),('A019','F406'),('A001','F406'),
('A002','F407'),('A003','F407'),('A004','F407'),
('A005','F408'),('A006','F408'),('A007','F408'),

-- BIG (6 attendants each)
('A001','F500'),('A002','F500'),('A003','F500'),('A004','F500'),('A006','F500'),('A007','F500'),
('A009','F501'),('A010','F501'),('A011','F501'),('A012','F501'),('A014','F501'),('A015','F501'),
('A016','F502'),('A017','F502'),('A018','F502'),('A019','F502'),('A001','F502'),('A002','F502'),
('A003','F503'),('A004','F503'),('A006','F503'),('A007','F503'),('A009','F503'),('A010','F503'),
('A011','F504'),('A012','F504'),('A014','F504'),('A015','F504'),('A017','F504'),('A018','F504'),
('A019','F505'),('A001','F505'),('A002','F505'),('A003','F505'),('A004','F505'),('A006','F505'),
('A007','F506'),('A009','F506'),('A010','F506'),('A011','F506'),('A012','F506'),('A014','F506'),
('A015','F507'),('A016','F507'),('A017','F507'),('A018','F507'),('A019','F507'),('A020','F507'),
('A001','F508'),('A003','F508'),('A005','F508'),('A007','F508'),('A009','F508'),('A011','F508'),
('A002','F509'),('A004','F509'),('A006','F509'),('A008','F509'),('A010','F509'),('A012','F509');

-- ============================================================
-- 3) F_ORDER (הרבה, חודשים שונים + ביטולים)
-- משתמשים במיילים שכבר קיימים אצלך:
-- Registered: roni / itay / maya
-- Guests: guest1/2/3
-- טיסות: F400..F509
-- ============================================================

INSERT INTO F_ORDER
(O_ID, FLIGHT_NUM, G_MAIL, R_MAIL, O_STATUS, O_DATE, ORDER_PRICE, USER_TYPE, CANACELATION_DATE_TIME)
VALUES

-- SEP 2025
('O400','F509','guest1@mail.com',NULL,'COMPLETED','2025-09-10',1800.00,'GUEST',NULL),
('O401','F408',NULL,'itay@gmail.com','COMPLETED','2025-09-12',1040.00,'REGISTERD',NULL),
('O402','F404','guest2@mail.com',NULL,'CUSTOMER_CANCELLED','2025-09-15',0.00,'GUEST','2025-09-20 11:00:00'),

-- OCT 2025
('O403','F404',NULL,'maya@gmail.com','COMPLETED','2025-10-05',1760.00,'REGISTERD',NULL),
('O404','F505','guest3@mail.com',NULL,'COMPLETED','2025-10-08',11000.00,'GUEST',NULL),
('O405','F503',NULL,'roni@gmail.com','SYSTEM_CANCELLED','2025-10-10',0.00,'REGISTERD','2025-10-18 09:30:00'),

-- NOV 2025
('O406','F403','guest1@mail.com',NULL,'COMPLETED','2025-11-02',1640.00,'GUEST',NULL),
('O407','F505',NULL,'itay@gmail.com','CUSTOMER_CANCELLED','2025-11-06',0.00,'REGISTERD','2025-11-15 14:00:00'),
('O408','F403',NULL,'roni@gmail.com','COMPLETED','2025-11-10',820.00,'REGISTERD',NULL),

-- DEC 2025
('O409','F403','guest2@mail.com',NULL,'SYSTEM_CANCELLED','2025-12-01',0.00,'GUEST','2025-12-05 10:00:00'),
('O410','F503','guest3@mail.com',NULL,'COMPLETED','2025-12-02',6950.00,'GUEST',NULL),
('O411','F403',NULL,'maya@gmail.com','CUSTOMER_CANCELLED','2025-12-03',0.00,'REGISTERD','2025-12-20 12:00:00'),

-- JAN 2026
('O412','F400','guest1@mail.com',NULL,'COMPLETED','2026-01-05',720.00,'GUEST',NULL),
('O413','F500',NULL,'roni@gmail.com','COMPLETED','2026-01-07',4720.00,'REGISTERD',NULL),
('O414','F501','guest2@mail.com',NULL,'COMPLETED','2026-01-09',2560.00,'GUEST',NULL),
('O415','F500','guest3@mail.com',NULL,'CUSTOMER_CANCELLED','2026-01-10',0.00,'GUEST','2026-01-12 08:00:00'),
('O416','F402',NULL,'itay@gmail.com','SYSTEM_CANCELLED','2026-01-11',0.00,'REGISTERD','2026-01-15 16:00:00'),

-- FEB 2026
('O417','F502',NULL,'maya@gmail.com','COMPLETED','2026-02-01',4980.00,'REGISTERD',NULL),
('O418','F402','guest1@mail.com',NULL,'COMPLETED','2026-02-02',1480.00,'GUEST',NULL),
('O419','F507','guest2@mail.com',NULL,'CUSTOMER_CANCELLED','2026-02-03',0.00,'GUEST','2026-02-10 09:00:00');

-- ============================================================
-- 4) ORDER_SEAT
-- כלל: אנחנו מכניסים מושבים רק להזמנות COMPLETED (כמו אצלך)
-- מושבים קיימים בוודאות:
--  * כל המטוסים: יש A-F בשורות 1.. (בגלל ה-generator)
--  * BIG: BUSINESS בשורות הראשונות (1..)
-- ============================================================

INSERT INTO ORDER_SEAT (O_ID, AIRCRAFT_ID, ROW_NUM, COL_LETTER) VALUES

-- O400: F509 uses AC004 (BIG) -> 2 economy seats (after business rows)
-- (ב-BIG הכל קיים, אז נשתמש בשורה 10)
('O400','AC004',10,'A'),
('O400','AC004',10,'B'),

-- O401: F408 uses AC003 (SMALL) -> 2 economy seats
('O401','AC003',1,'A'),
('O401','AC003',1,'B'),

-- O403: F404 uses AC003 (SMALL) -> 2 seats
('O403','AC003',2,'A'),
('O403','AC003',2,'B'),

-- O404: F505 uses AC006 (BIG) -> 2 BUSINESS + 2 ECONOMY
('O404','AC006',1,'A'),
('O404','AC006',1,'B'),
('O404','AC006',10,'A'),
('O404','AC006',10,'B'),

-- O406: F403 uses AC002 (SMALL) -> 2 seats
('O406','AC002',1,'A'),
('O406','AC002',1,'B'),

-- O408: F403 uses AC002 (SMALL) -> 1 seat
('O408','AC002',2,'A'),

-- O410: F503 uses AC004 (BIG) -> 1 BUSINESS + 2 ECONOMY
('O410','AC004',1,'C'),
('O410','AC004',10,'C'),
('O410','AC004',10,'D'),

-- O412: F400 uses AC001 (SMALL) -> 2 seats
('O412','AC001',1,'A'),
('O412','AC001',1,'B'),

-- O413: F500 uses AC004 (BIG) -> 1 BUSINESS + 2 ECONOMY
('O413','AC004',1,'A'),
('O413','AC004',11,'A'),
('O413','AC004',11,'B'),

-- O414: F501 uses AC005 (BIG) -> 2 BUSINESS + 1 ECONOMY
('O414','AC005',1,'A'),
('O414','AC005',1,'B'),
('O414','AC005',10,'A'),

-- O417: F502 uses AC006 (BIG) -> 2 ECONOMY seats
('O417','AC006',12,'A'),
('O417','AC006',12,'B'),

-- O418: F402 uses AC002 (SMALL) -> 2 seats
('O418','AC002',3,'A'),
('O418','AC002',3,'B');


-- =========================
-- MANAGER (2)
-- =========================
INSERT INTO MANAGER (ID_M, H_FIRST_NAME, H_LAST_NAME, PHONE_NUM, CITY, STREET, HOUSE_NUM, START_DATE, M_PASSWORD) VALUES
('212290241','עמית','לבבי','0503333333','Tel Aviv','Ibn Gabirol',10,'2022-01-10','123'),
('23000000','גל','הראל','0524444444','Jerusalem','Jaffa',25,'2021-06-01','123');

INSERT INTO ROUTE (ROUTE_ID, DURATION, ORIGIN, DESTINATION) VALUES
-- ---------- Reverse routes for existing R001-R024 ----------
('R025','01:10:00','LCA','TLV'),
('R026','02:20:00','ATH','TLV'),
('R027','05:45:00','LHR','TLV'),
('R028','06:00:00','MAD','TLV'),
('R029','06:30:00','DXB','TLV'),
('R030','08:15:00','JFK','TLV'),
('R031','04:30:00','CDG','TLV'),
('R032','03:55:00','FCO','TLV'),
('R033','03:40:00','AMS','TLV'),
('R034','02:55:00','VIE','TLV'),
('R035','03:10:00','BER','TLV'),
('R036','04:20:00','BCN','TLV'),
('R037','05:20:00','ZRH','TLV'),
('R038','02:10:00','SOF','TLV'),
('R039','01:55:00','IST','TLV'),
('R040','04:05:00','PRG','TLV'),
('R041','03:35:00','BUD','TLV'),
('R042','05:00:00','FRA','TLV'),
('R043','10:45:00','BKK','TLV'),
('R044','12:00:00','HND','TLV'),
('R045','07:20:00','YYZ','TLV'),
('R046','09:30:00','SFO','TLV'),
('R047','06:45:00','DEL','TLV'),
('R048','07:10:00','SIN','TLV'),

-- ---------- New routes (invented) + their reverse ----------
('R049','04:10:00','TLV','MUC'),
('R050','04:10:00','MUC','TLV'),

('R051','05:05:00','TLV','ARN'),
('R052','05:05:00','ARN','TLV'),

('R053','04:45:00','TLV','CPH'),
('R054','04:45:00','CPH','TLV'),

('R055','05:40:00','TLV','LIS'),
('R056','05:40:00','LIS','TLV'),

('R057','05:55:00','TLV','OPO'),
('R058','05:55:00','OPO','TLV'),

('R059','01:25:00','TLV','CAI'),
('R060','01:25:00','CAI','TLV'),

('R061','13:10:00','TLV','LAX'),
('R062','13:10:00','LAX','TLV'),

('R063','12:15:00','TLV','MIA'),
('R064','12:15:00','MIA','TLV');

