-- MySQL 8.4 schema reference, generated from app/db.py.

-- Use python -m app.manage migrate for installation, not both paths.

CREATE TABLE terms (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	revision INTEGER NOT NULL, 
	published INTEGER, 
	policy JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE resources (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	kind VARCHAR(12) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	size INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (kind, name)
);

CREATE TABLE versions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	input_revision INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	state VARCHAR(12) NOT NULL, 
	snapshot JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE jobs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	`key` VARCHAR(100) NOT NULL, 
	revision INTEGER NOT NULL, 
	snapshot JSON NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	owner VARCHAR(64), 
	lease DOUBLE NOT NULL, 
	attempts INTEGER NOT NULL, 
	result JSON, 
	PRIMARY KEY (id), 
	UNIQUE (`key`)
);

CREATE TABLE audit (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	at DOUBLE NOT NULL, 
	actor VARCHAR(100) NOT NULL, 
	action VARCHAR(60) NOT NULL, 
	details JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE outbox (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	message VARCHAR(300) NOT NULL, 
	delivered BOOL NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE requirements (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	course VARCHAR(100) NOT NULL, 
	teacher INTEGER NOT NULL, 
	cohort INTEGER NOT NULL, 
	sessions INTEGER NOT NULL, 
	duration INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(teacher) REFERENCES resources (id), 
	FOREIGN KEY(cohort) REFERENCES resources (id)
);

CREATE TABLE blocks (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	resource INTEGER NOT NULL, 
	slot INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (resource, slot), 
	FOREIGN KEY(resource) REFERENCES resources (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(100) NOT NULL, 
	password VARCHAR(256) NOT NULL, 
	`role` VARCHAR(12) NOT NULL, 
	teacher INTEGER, 
	failed INTEGER NOT NULL, 
	locked_until DOUBLE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username), 
	FOREIGN KEY(teacher) REFERENCES resources (id)
);

CREATE TABLE login_sessions (
	token VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	csrf VARCHAR(64) NOT NULL, 
	expires DOUBLE NOT NULL, 
	PRIMARY KEY (token), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE lessons (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	version INTEGER NOT NULL, 
	requirement INTEGER NOT NULL, 
	teacher INTEGER NOT NULL, 
	cohort INTEGER NOT NULL, 
	room INTEGER NOT NULL, 
	slot INTEGER NOT NULL, 
	duration INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(version) REFERENCES versions (id), 
	FOREIGN KEY(requirement) REFERENCES requirements (id), 
	FOREIGN KEY(teacher) REFERENCES resources (id), 
	FOREIGN KEY(cohort) REFERENCES resources (id), 
	FOREIGN KEY(room) REFERENCES resources (id)
);

CREATE INDEX ix_lesson_cohort ON lessons (version, cohort, slot);

CREATE INDEX ix_lesson_teacher ON lessons (version, teacher, slot);

CREATE TABLE notices (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	event INTEGER NOT NULL, 
	user INTEGER NOT NULL, 
	message VARCHAR(300) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (event, user), 
	FOREIGN KEY(event) REFERENCES outbox (id), 
	FOREIGN KEY(user) REFERENCES users (id)
);

CREATE TABLE occupancy (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	version INTEGER NOT NULL, 
	lesson INTEGER NOT NULL, 
	resource INTEGER NOT NULL, 
	slot INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (version, resource, slot), 
	FOREIGN KEY(version) REFERENCES versions (id), 
	FOREIGN KEY(lesson) REFERENCES lessons (id), 
	FOREIGN KEY(resource) REFERENCES resources (id)
);

CREATE TABLE exceptions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	version INTEGER NOT NULL, 
	lesson INTEGER NOT NULL, 
	date VARCHAR(10) NOT NULL, 
	cancelled BOOL NOT NULL, 
	slot INTEGER, 
	room INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (version, lesson, date), 
	FOREIGN KEY(version) REFERENCES versions (id), 
	FOREIGN KEY(lesson) REFERENCES lessons (id), 
	FOREIGN KEY(room) REFERENCES resources (id)
);

ALTER TABLE terms ADD FOREIGN KEY(published) REFERENCES versions (id);
