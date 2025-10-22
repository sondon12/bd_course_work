Create table Breeds
(
  id_breed numeric(3) PRIMARY KEY,
  name text NOT NULL,
  characteristic text,
  height_max integer CHECK(height_max < 120),
  height_min integer CHECK(height_min > 10),
  CONSTRAINT height_breed CHECK (height_min < height_max),
  color text
);

Create table Dogs
(
  id_dog serial PRIMARY KEY,
  id_breed numeric(3) NOT NULL,
  owner text,
  adress text,
  alive bool DEFAULT TRUE,
  assesment real NOT NULL,
  CONSTRAINT valid_assesment CHECK(0< assesment AND assesment<=10),
  gender char(1) NOT NULL,
  CONSTRAINT valid_gender CHeck(gender = 'M' OR gender = 'F'),
  FOREIGN KEY (id_breed)
  REFERENCES Breeds ( id_breed )
  ON DELETE CASCADE
  ON UPDATE CASCADE
);


CREATE TABLE Parents
(
  id_dog serial NOT NULL,
  id_mother serial REFERENCES Dogs(id_dog),
  id_father serial REFERENCES Dogs(id_dog),
  FOREIGN KEY (id_dog)
  REFERENCES Dogs (id_dog)
  ON DELETE CASCADE
  ON UPDATE CASCADE
);

CReate table Exhibitions
(
  id_dog serial,
  date_exhibition date,
  mark integer,
  medal text,
  name text,
  CONSTRAINT valid_medal CHECK(medal = 'Gold' OR medal = 'Silver' OR medal = 'Bronze'),
  CONSTRAINT valid_mark CHECK(mark > 0 AND mark <=12),
  FOREIGN KEY (id_dog)
  REFERENCES Dogs (id_dog)
  ON DELETE CASCADE
  ON UPDATE CASCADE
);

CREATE TABLE Medicine_book
(
  id_illness numeric(4) PRIMARY KEY,
  name text,
  method text
);

Create table Medicine_history
(
  id_dog serial REFERENCES Dogs(id_dog),
  id_illness numeric(4),
  start_date date,
  end_date date,
  FOREIGN KEY (id_illness)
  REFERENCES Medicine_book (id_illness)
  ON DELETE CASCADE
  ON UPDATE CASCADE
);