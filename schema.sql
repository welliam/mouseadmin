create table Template (
  id integer primary key,
  timestamp datetime default current_timestamp,
  name text not null,
  neocities_path text not null,
  entry_path_template text not null,
  entry_template text not null,
  index_template text not null,
  unique (neocities_path)
);

create table TemplateField (
  id integer primary key,
  timestamp datetime default current_timestamp,
  template_id integer,
  field_name text not null,
  field_type text not null,
  field_options text, -- json array
  foreign key (template_id) references Template(id)
);

create table TemplateEntry (
  id integer primary key,
  timestamp datetime default current_timestamp,
  last_updated datetime,
  template_id integer,
  foreign key (template_id) references Template(id)
);

create table TemplateFieldValue (
  id integer primary key,
  timestamp datetime default current_timestamp,
  template_entry_id integer not null,
  template_field_id integer not null,
  value_json text,
  value_blob blob,
  foreign key (template_entry_id) references TemplateEntry(id),
  foreign key (template_field_id) references TemplateField(id)
);
