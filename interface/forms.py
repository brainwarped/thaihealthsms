# -*- encoding: utf-8 -*-
import datetime

from django import forms
from django.forms.util import ErrorList
from django.contrib.formtools.wizard import FormWizard
from django.contrib.admin import widgets
from django.contrib.auth.models import User, Group
from domain.models import *
from report.models import *

from django.http import HttpResponseRedirect
from helper.utilities import set_message

from widgets import YUICalendar

month_cycle = [(i,i) for i in range(1,13)]
date_cycle = [(0, 'วันสิ้นเดือน'),(1,1),(2,2),(3,3),(4,4),(5,5),(6,6),(7,7),(8,8),(9,9),(10,10),(11,11),(12,12),(13,13),(14,14),(15,15),(16,16),(17,17),(18,18),(19,19),(20,20),(21,21),(22,22),(23,23),(24,24),(25,25),(26,26),(27,27),(28,28),(29,29),(30,30),(31,31)]

sectors = [(sector.id, '%s %s' % (sector.ref_no, sector.name)) for sector in Sector.objects.all().order_by('ref_no')]
roles = [(group_name.group.name, group_name.name) for group_name in GroupName.objects.all()]

class UserAccountForm(forms.Form):
	username = forms.CharField(max_length=500, label='ชื่อผู้ใช้')
	email = forms.EmailField(label='อีเมล')
	first_name = forms.CharField(max_length=500, required=False, label='ชื่อจริง')
	last_name = forms.CharField(max_length=500, required=False, label='นามสกุล')
	role = forms.CharField(widget=forms.Select(choices=roles), label='ตำแหน่ง')
	sector = forms.IntegerField(widget=forms.Select(choices=sectors), label='สังกัดสำนัก')
	responsible = forms.IntegerField(widget=forms.HiddenInput(), required=False, label='เลือกแผนหลัก จากนั้นเลือกแผนงานที่รับผิดชอบ')

class ChangeFirstTimePasswordForm(forms.Form):
	password1 = forms.CharField(widget=forms.PasswordInput(), max_length=100, label='รหัสผ่าน')
	password2 = forms.CharField(widget=forms.PasswordInput(), max_length=100, label='ยืนยันรหัสผ่าน')

	def clean(self):
		cleaned_data = self.cleaned_data
		password1 = cleaned_data.get('password1')
		password2 = cleaned_data.get('password2')

		if password1 != password2:
			self._errors["password2"] = ErrorList(['รหัสผ่านไม่สัมพันธ์กัน'])
			del cleaned_data["password2"]

		return cleaned_data

class ChangePasswordForm(forms.Form):
	username = forms.CharField(max_length=500, label='ชื่อผู้ใช้')
	old_password = forms.CharField(widget=forms.PasswordInput(), max_length=100, label='รหัสผ่านเก่า')
	new_password1 = forms.CharField(widget=forms.PasswordInput(), max_length=100, label='รหัสผ่านใหม่')
	new_password2 = forms.CharField(widget=forms.PasswordInput(), max_length=100, label='ยืนยันรหัสผ่านใหม่')

	def clean(self):
		cleaned_data = self.cleaned_data
		username = cleaned_data.get('username')
		old_password = cleaned_data.get('old_password')
		new_password1 = cleaned_data.get('new_password1')
		new_password2 = cleaned_data.get('new_password2')

		if new_password1 != new_password2:
			self._errors["new_password2"] = ErrorList(['รหัสผ่านไม่สัมพันธ์กัน'])
			del cleaned_data["new_password2"]

		from django.contrib.auth.models import User

		try:
			user = User.objects.get(username=username)
		except User.DoesNotExist:
			self._errors["username"] = ErrorList(['ไม่พบผู้ใช้นี้ในระบบ'])
			del cleaned_data["username"]
		else:
			from django.contrib.auth.models import check_password

			if not check_password(old_password, user.password):
				self._errors["old_password"] = ErrorList(['รหัสผ่านไม่ถูกต้อง'])
				del cleaned_data["old_password"]

		return cleaned_data

class SectorChoiceField(forms.ModelChoiceField):
	def label_from_instance(self, obj):
		return "%d %s" % (obj.id, obj.name)

class PlanChoiceField(forms.ModelChoiceField):
	def label_from_instance(self, obj):
		return "%s %s" % (obj.ref_no, obj.name)

class ReportMultipleChoiceField(forms.ModelMultipleChoiceField):
	def label_from_instance(self, obj):
		return "%s" % obj.name

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

class EditMasterPlanForm(forms.Form):
	ref_no = forms.IntegerField(label='รหัส')
	name = forms.CharField(max_length=512, label='ชื่อแผน')
	sector = forms.IntegerField(widget=forms.Select(choices=sectors), label='สังกัดสำนัก')

#
# Sector Form
#
class SectorForm(forms.Form):
	ref_no = forms.IntegerField(label='เลขสำนัก')
	name = forms.CharField(max_length=512, label='ชื่อสำนัก')

class SectorReportForm(forms.Form):
	name = forms.CharField(max_length=512, label='ชื่อรายงาน')
	need_approval = forms.BooleanField(required=False, label='รายงานที่ส่งมา ต้องมีการรับรองรายงาน')
	schedule_cycle_length = forms.ChoiceField(choices=month_cycle)
	schedule_monthly_date = forms.ChoiceField(choices=date_cycle)
	notify_days = forms.IntegerField(label='จำนวนวันที่แจ้งเตือนผู้ดูแลโครงการก่อนรายงานจะถึงกำหนดส่ง')

#
# Master Plan Form
#
class PlanChoiceField(forms.ModelChoiceField):
	def label_from_instance(self, obj):
		return "%s %s" % (obj.ref_no, obj.name)

class ReportMultipleChoiceField(forms.ModelMultipleChoiceField):
	def label_from_instance(self, obj):
		return "%s" % obj.name

class MasterPlanAddProjectForm(forms.Form):
	plan = PlanChoiceField(queryset=Plan.objects.all(), label="สังกัดกลุ่มแผนงาน", empty_label=None)
	ref_no = forms.CharField(max_length=64, label='เลขที่โครงการ')
	name = forms.CharField(max_length=512, label='ชื่อโครงการ')
	description = forms.CharField(widget=forms.Textarea(), required=False, label='รายละเอียด')
	start_date = forms.DateField(widget=YUICalendar(attrs={'id':'id_start_date'}), label='เริ่ม')
	end_date = forms.DateField(widget=YUICalendar(attrs={'id':'id_end_date'}), label='ถึง')
	reports = ReportMultipleChoiceField(queryset=Report.objects.all(), label="รายงานที่ต้องส่ง")

class MasterPlanEditProjectForm(forms.Form):
	plan = PlanChoiceField(queryset=Plan.objects.all(), label="สังกัดกลุ่มแผนงาน", empty_label=None)
	ref_no = forms.CharField(max_length=64, label='เลขที่โครงการ')
	name = forms.CharField(max_length=512, label='ชื่อโครงการ')
	description = forms.CharField(widget=forms.Textarea(), required=False, label='รายละเอียด')
	reports = ReportMultipleChoiceField(queryset=Report.objects.all(), label="รายงานที่ต้องส่ง")

#
# Plan Form
#
class PlanForm(forms.Form):
	ref_no = forms.CharField(max_length=512, label='รหัส')
	name = forms.CharField(max_length=512, label='ชื่อกลุ่มแผนงาน')

#
# Project Form
#
class ProjectForm(forms.Form):
	ref_no = forms.CharField(max_length=64, label='เลขที่โครงการ')
	name = forms.CharField(max_length=512, label='ชื่อโครงการ')
	start_date = forms.DateField(widget=YUICalendar(attrs={'id':'id_start_date'}), label='ระยะเวลาโครงการ')
	end_date = forms.DateField(widget=YUICalendar(attrs={'id':'id_end_date'}), label='ถึง')

class AddProjectReportForm(forms.Form):
	name = forms.CharField(max_length=512, label='ชื่อรายงาน')
	need_checkup = forms.BooleanField(required=False, label='ส่งรายงานถึงผู้ประสานงานสำนัก')
	need_approval = forms.BooleanField(required=False, label='ต้องรับรองรายงาน')
	schedule_cycle_length = forms.ChoiceField(choices=month_cycle)
	schedule_monthly_date = forms.ChoiceField(choices=date_cycle)
	start_date = forms.DateField(widget=YUICalendar(attrs={'id':'id_start_date'}), label='เริ่มตั้งแต่วันที่')
	end_date = forms.DateField(widget=YUICalendar(attrs={'id':'id_end_date'}), label='ถึง')

class EditProjectReportForm(forms.Form):
	name = forms.CharField(max_length=512, label='ชื่อรายงาน')
	need_checkup = forms.BooleanField(required=False, label='ส่งรายงานถึงผู้ประสานงานสำนัก')
	need_approval = forms.BooleanField(required=False, label='ต้องรับรองรายงาน')

#
# Activity Form
#
class ActivityForm(forms.Form):
	name 			= forms.CharField(max_length=500, label='ชื่อกิจกรรม')
	start_date      = forms.DateField(widget=YUICalendar(attrs={'id':'id_start_date'}), label='เริ่มตั้งแต่วันที่', required=False)
	end_date        = forms.DateField(widget=YUICalendar(attrs={'id':'id_end_date'}), label='ถึง', required=False)
	description 	= forms.CharField(max_length=2000, required=False, widget=forms.Textarea(), label='รายละเอียด')
	location 		= forms.CharField(max_length=2000, required=False, label='สถานที่')
	result_goal 	= forms.CharField(max_length=2000, required=False, widget=forms.Textarea(), label='ผลลัพธ์ที่ต้องการ')
	result_real 	= forms.CharField(max_length=2000, required=False, widget=forms.Textarea(), label='ผลลัพธ์ที่เกิดขึ้น')
