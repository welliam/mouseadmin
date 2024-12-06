CREATE TABLE TemplateFieldValueNew (
  id integer primary key,
  timestamp datetime default current_timestamp,
  template_entry_id integer not null,
  template_field_name text,
  template_field_id integer not null, -- to drop
  value_json text,
  value_blob blob,
  foreign key (template_entry_id) references TemplateEntry(id),
  foreign key (template_field_name) references TemplateField(name)
);

INSERT INTO TemplateFieldValueNew (
    id,
    timestamp,
    template_entry_id,
    template_field_id,
    value_json,
    value_blob
) SELECT id, timestamp, template_entry_id, template_field_id, value_json, value_blob FROM TemplateFieldValue;

DROP TABLE TemplateFieldValue;
ALTER TABLE TemplateFieldValueNew RENAME TO TemplateFieldValue;

update TemplateFieldValue set template_field_name='title' where template_field_id=1;
update TemplateFieldValue set template_field_name='developer' where template_field_id=2;
update TemplateFieldValue set template_field_name='rating' where template_field_id=3;
update TemplateFieldValue set template_field_name='art_url' where template_field_id=4;
update TemplateFieldValue set template_field_name='platform' where template_field_id=5;
update TemplateFieldValue set template_field_name='completion' where template_field_id=6;
update TemplateFieldValue set template_field_name='method' where template_field_id=7;
update TemplateFieldValue set template_field_name='date' where template_field_id=8;
update TemplateFieldValue set template_field_name='emulated' where template_field_id=9;
update TemplateFieldValue set template_field_name='review' where template_field_id=10;
update TemplateFieldValue set template_field_name='recommendation' where template_field_id=11;
update TemplateFieldValue set template_field_name='extras' where template_field_id=12;

update TemplateFieldValue set template_field_name='title' where template_field_id=13;
update TemplateFieldValue set template_field_name='year' where template_field_id=14;
update TemplateFieldValue set template_field_name='month' where template_field_id=15;
update TemplateFieldValue set template_field_name='date' where template_field_id=16;
update TemplateFieldValue set template_field_name='media' where template_field_id=17;
update TemplateFieldValue set template_field_name='characters' where template_field_id=18;
update TemplateFieldValue set template_field_name='image_url' where template_field_id=19;
update TemplateFieldValue set template_field_name='mythot' where template_field_id=20;
update TemplateFieldValue set template_field_name='postit_color' where template_field_id=21;

alter table TemplateFieldValue drop column template_field_id;
