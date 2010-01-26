# -*- encoding: utf-8 -*-
import datetime

from django import forms
from django.contrib.formtools.wizard import FormWizard
from django.contrib.admin import widgets
from django.contrib.auth.models import User, Group
from domain.models import *

from django.http import HttpResponseRedirect
from helper.utilities import set_message

from widgets import YUICalendar

class ActivityForm(forms.Form):
	name 			= forms.CharField(max_length=500, label='ชื่อกิจกรรม')
	start_date      = forms.DateField(widget=YUICalendar(attrs={'id':'id_start_date'}), label='เริ่มตั้งแต่วันที่', required=False)
	end_date        = forms.DateField(widget=YUICalendar(attrs={'id':'id_end_date'}), label='ถึง', required=False)
	description 	= forms.CharField(max_length=2000, required=False, widget=forms.Textarea(), label='รายละเอียด')
	location 		= forms.CharField(max_length=2000, required=False, label='สถานที่')
	result_goal 	= forms.CharField(max_length=2000, required=False, widget=forms.Textarea(), label='ผลลัพธ์ที่ต้องการ')
	result_real 	= forms.CharField(max_length=2000, required=False, widget=forms.Textarea(), label='ผลลัพธ์ที่เกิดขึ้น')

sectors = [(sector.id, '%s %s' % (sector.ref_no, sector.name)) for sector in Sector.objects.all().order_by('ref_no')]
roles = [(group_name.group.name, group_name.name) for group_name in GroupName.objects.all()]

class UserAccountFormStart(forms.Form):
	username = forms.CharField(max_length=500, label='ชื่อผู้ใช้')
	email = forms.EmailField()
	password = forms.CharField(widget=forms.PasswordInput(),required=False, label='รหัสผ่าน')
	password_confirm = forms.CharField(widget=forms.PasswordInput(),required=False, label='ยืนยันรหัสผ่าน')
	first_name = forms.CharField(max_length=500, required=False, label='ชื่อจริง')
	last_name = forms.CharField(max_length=500, required=False, label='นามสกุล')
	role = forms.CharField(widget=forms.Select(choices=roles), label='ตำแหน่ง')
	sector = forms.IntegerField(widget=forms.Select(choices=sectors), label='สังกัดสำนัก')

	def clean_password_confirm(self):
		password = self.cleaned_data.get('password', '')
		password_confirm = self.cleaned_data.get('password_confirm', '')

		if password != password_confirm:
			raise forms.ValidationError('Password not match')
		return password

	def clean_project(self):
		return self.cleaned_data.get('project', [])

class UserAccountFormSecond(forms.Form):
	pass

class UserAccountWizard(FormWizard):
	def parse_params(self, request, *args, **kwargs):
		user_id = kwargs.get('user_id', 0)

		self.user = False
		if user_id:
			user = User.objects.get(pk=user_id)
			self.user = user
			user_account = user.get_profile()
			user_responsibility = UserRoleResponsibility.objects.get(user=user_account)

			initial = {}

			initial[0] = user.__dict__.copy()
			initial[0].update(user_account.__dict__.copy())
			initial[0].update(user_responsibility.__dict__.copy())

			initial[0]['password'] = ''
			initial[0]['sector'] = user_account.sector.id
			initial[0]['role'] = user_responsibility.role.name

			initial[1] = {}
			if user_responsibility.projects.count():
				initial[1]['program'] = user_responsibility.projects.all()[0].id
				initial[1]['project'] = [project.id for project in user_responsibility.projects.all()]

			self.initial = initial

	def get_template(self, step):
		return 'administer_users_add.html'

	def process_step(self, request, form, step):
		if step == 0 and form.is_valid():
			group_name = form.cleaned_data.get('role', '')
			sector_id = form.cleaned_data.get('sector', 0)

			if group_name == 'sector_admin' or group_name == 'sector_manager':
				if len(self.form_list) > 1:
					del(self.form_list[1])

			elif group_name == 'sector_manager_assistant':
				projects_obj = Project.objects.filter(sector__id=sector_id, prefix_name=Project.PROJECT_IS_PROJECT, parent_project=None)
				projects = [(project.id, '%s %s' % (project.ref_no, project.name)) for project in projects_obj]

				class UserAccountFormForSector(forms.Form):
					project = forms.MultipleChoiceField(choices=projects, required=False, label='โครงการ')

				if len(self.form_list) == 1:
					self.form_list.append(UserAccountFormForSector)
				else:
					self.form_list[1] = UserAccountFormForSector

			elif group_name in ('project_manager', 'project_manager_assistant'):
				programs_obj = Project.objects.filter(sector__id=sector_id, prefix_name=Project.PROJECT_IS_PROGRAM)
				programs = [(program.id, '%s %s' % (program.ref_no, program.name)) for program in programs_obj]

				class UserAccountFormForProgram(forms.Form):
					program = forms.IntegerField(widget=forms.Select(choices=programs), required=False, label='แผนงาน')

				if len(self.form_list) == 1:
					self.form_list.append(UserAccountFormForProgram)
				else:
					self.form_list[1] = UserAccountFormForProgram

	def done(self, request, form_list):
		form = {}
		for form_item in form_list:
			form.update(form_item.cleaned_data)

		sector = Sector.objects.get(id=form.get('sector', 0))

		if self.user:
			user = self.user
			user.username = form.get('username', '')
			user.email = form.get('email', '')

			password = form.get('password', '')
			if password:
				user.set_password(password)

			user.save()
		else:
			user = User.objects.create_user(form.get('username', ''), form.get('email', ''), form.get('password', ''))

		user_account = user.get_profile()
		user_account.first_name = form.get('first_name', ''),
		user_account.last_name = form.get('last_name', ''),
		user_account.sector = sector
		user_account.save()

		group_name = form.get('role', '')
		if self.user:
			user_responsibility = UserRoleResponsibility.objects.filter(user=user_account).delete()

		user_responsibility = UserRoleResponsibility.objects.create(
			user = user_account,
			role = Group.objects.get(name=group_name)
		)


		if group_name == 'sector_admin' or group_name == 'sector_manager':
			user_responsibility.sectors.add(sector)
		elif group_name == 'sector_manager_assistant':
			user_responsibility.sectors.add(sector)
			for project in Project.objects.filter(pk__in=form.get('project', [])):
				user_responsibility.projects.add(project)
		elif group_name in ('project_manager', 'project_manager_assistant'):
			program = Project.objects.get(pk=form.get('program', 0))
			user_responsibility.projects.add(program)

		if self.user:
			set_message(request, 'Your user has been update.')
		else:
			set_message(request, 'Your user has been create.')

		return HttpResponseRedirect('/administer/users/')

class SectorForm(forms.Form):
	ref_no = forms.IntegerField(label='เลขสำนัก')
	name = forms.CharField(max_length=512, label='ชื่อสำนัก')

class SectorReportForm(forms.Form):
	name = forms.CharField(max_length=512, label='ชื่อรายงาน')
	need_approval = forms.BooleanField(required=False, label='ต้องรับรองรายงาน')

class SectorChoiceField(forms.ModelChoiceField):
	def label_from_instance(self, obj):
		return "%d %s" % (obj.id, obj.name)

class MasterPlanForm(forms.Form):
	'''MasterPlan adding form'''

	ref_no = forms.IntegerField(label='รหัส')
	name = forms.CharField(max_length=512, label='ชื่อแผน')
	sector = SectorChoiceField(required=True, queryset=Sector.objects.all().order_by('ref_no'), empty_label=None, label='สังกัดสำนัก')
	year_start = forms.IntegerField(label='ช่วงปี')
	year_end = forms.IntegerField(label='ถึง')

	def clean(self):
		"Check if year_start and year_end is valid."

		cleaned_data = self.cleaned_data
		year_start = cleaned_data.get('year_start')
		year_end = cleaned_data.get('year_end')

		# Convert B.E. to C.E.
		thai_year_start = year_start - 543
		thai_year_end = year_end - 543
		try:
			thai_date_start = datetime.date(thai_year_start, 1, 1)
			thai_date_end = datetime.date(thai_year_end, 1, 1)

			if thai_date_start > thai_date_end:
				raise forms.ValidationError("Start year must greater than end year")
		except ValueError:
			raise forms.ValidationError("Year is not valid.")

		return cleaned_data

month_cycle = [(i,i) for i in range(1,13)]
date_cycle = [(i,i) for i in range(1,32)]

class AddProjectReportForm(forms.Form):
	name = forms.CharField(max_length=512, label='ชื่อรายงาน')
	need_checkup = forms.BooleanField(required=False, label='ส่งรายงานถึงผู้ประสานงานสำนัก')
	need_approval = forms.BooleanField(required=False, label='ต้องรับรองรายงาน')
	month_cycle = forms.ChoiceField(label='ส่งรายงานทุกๆ', choices=month_cycle)
	on_every = forms.CharField(widget=forms.HiddenInput())
	on_every_date = forms.ChoiceField(required=False, choices=date_cycle)
	start_date = forms.DateField(widget=YUICalendar(attrs={'id':'id_start_date'}), label='เริ่มตั้งแต่วันที่')
	end_date = forms.DateField(widget=YUICalendar(attrs={'id':'id_end_date'}), label='ถึง')

class EditProjectReportForm(forms.Form):
	name = forms.CharField(max_length=512, label='ชื่อรายงาน')
	need_checkup = forms.BooleanField(required=False, label='ส่งรายงานถึงผู้ประสานงานสำนัก')
	need_approval = forms.BooleanField(required=False, label='ต้องรับรองรายงาน')

class EditMasterPlanForm(forms.Form):
	ref_no = forms.IntegerField(label='รหัส')
	name = forms.CharField(max_length=512, label='ชื่อแผน')
	sector = forms.IntegerField(widget=forms.Select(choices=sectors), label='สังกัดสำนัก')

class ProjectForm(forms.Form):
	ref_no = forms.CharField(max_length=64, label='เลขที่โครงการ')
	name = forms.CharField(max_length=512, label='ชื่อโครงการ')
	description = forms.CharField(widget=forms.Textarea(), required=False, label='รายละเอียด')
	start_date = forms.DateField(widget=widgets.AdminDateWidget, label='เริ่ม')
	end_date = forms.DateField(widget=widgets.AdminDateWidget, label='ถึง')
	
