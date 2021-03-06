import re
import warnings
from django.core.management.commands.inspectdb import Command as InspectDBCommand
from django.db import connections, DEFAULT_DB_ALIAS
import django
import salesforce

class Command(InspectDBCommand):
	# This will export Salestorce to a valid models.py, if Django >=1.5.
	# It is recommended to use Django >=1.5 for inspectdb, even if the generated models.py will be used on Django <1.5
	# (The model generated by Django <=1.4 requires very much manual editing, adding many `related_name=...`)

	def handle_noargs(self, **options):
		self.connection = connections[options['database']]
		if self.connection.vendor == 'salesforce':
			self.db_module = 'salesforce'
			for line in self.handle_inspection(options):
				line = line.replace(" Field renamed because it contained more than one '_' in a row.", "")
				line = re.sub(' #$', '', line)
				if django.VERSION[:2] < (1,5):
					# prevent problems with mutual dependencies etc.
					line = re.sub(r'(?<=models.ForeignKey\()(\w+)',  r"'\1'", line)
				elif django.VERSION[:2] == (1,5):
					# fix bug in Django 1.5
					line = line.replace("''self''", "'self'")
				self.stdout.write("%s\n" % line)
		else:
			super(Command, self).handle_noargs(self, **options)


	def get_field_type(self, connection, table_name, row):
		field_type, field_params, field_notes = super(Command, self).get_field_type(connection, table_name, row)
		if connection.vendor == 'salesforce':
			name, type_code, display_size, internal_size, precision, scale, null_ok, sf_params = row
			field_params.update(sf_params)
		return field_type, field_params, field_notes

	def normalize_col_name(self, col_name, used_column_names, is_relation):
		new_name, field_params, field_notes = super(Command, self).normalize_col_name(col_name, used_column_names, is_relation)
		if self.connection.vendor == 'salesforce':
			if is_relation:
				if col_name.lower().endswith('_id'):
					field_params['db_column'] = col_name[:-3] + col_name[-2:]
				if field_params['db_column'] in salesforce.backend.introspection.last_with_important_related_name:
					field_params['related_name'] = ('%s_%s_set' % (
						salesforce.backend.introspection.last_introspected_model,
						re.sub('_Id$', '', new_name).replace('_', '')
						)).lower()
				if field_params['db_column'] in  salesforce.backend.introspection.last_read_only:
					field_params['sf_read_only'] = salesforce.backend.introspection.last_read_only[field_params['db_column']]
			field_notes = [x for x in field_notes if x != 'Field name made lowercase.']
		return new_name, field_params, field_notes

	def get_meta(self, table_name):
		"""
		Return a sequence comprising the lines of code necessary
		to construct the inner Meta class for the model corresponding
		to the given database table name.
		"""
		ret =  ["    class Meta(models.SalesforceModel.Meta):",
			"        db_table = '%s'" % table_name,
			]
		if self.connection.vendor == 'salesforce':
			for line in self.connection.introspection.get_additional_meta(table_name):
				ret.append("        " + line)
		ret.append("")
		return ret


if django.VERSION[:2] < (1,5):
	warnings.warn("Django >= 1.5 is required to generate a valid model. "
			"Manual editing is necessary for older Django.")
