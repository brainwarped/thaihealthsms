# -*- encoding: utf-8 -*-

import calendar
from datetime import datetime, date
import os

from django.db.models import Q
from django.db.models import F

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.core import serializers
from django.utils import simplejson

from thaihealthsms.shortcuts import render_response, access_denied

from comments.models import *
from domain.models import *
from report.models import *

from interface.forms import *

from domain import functions as domain_functions
from report import functions as report_functions
from helper import utilities

def view_frontpage(request):
	if request.user.is_authenticated(): return view_dashboard(request)
	else: return redirect("/accounts/login/")

from django.contrib.auth.views import login
from django.contrib.auth import REDIRECT_FIELD_NAME

def hooked_login(request, template_name='registration/login.html', redirect_field_name=REDIRECT_FIELD_NAME):
	response = login(request, template_name, redirect_field_name)
	
	if request.user.is_authenticated():
		if not request.user.is_superuser and request.user.get_profile().random_password:
			
			return redirect('/accounts/first_time/')
	
	return response

@login_required
def view_first_time_login(request):
	
	if request.user.is_authenticated():
		if request.user.is_superuser or (not request.user.is_superuser and not request.user.get_profile().random_password):
			return redirect('/')
	
	if request.method == 'POST':
		form = ChangeFirstTimePasswordForm(request.POST)
		if form.is_valid():
			password1 = form.cleaned_data['password1']
			password2 =form.cleaned_data['password2']
			
			user = request.user
			user.set_password(password1)
			user.save()
			
			user_account = user.get_profile()
			user_account.random_password = ''
			user_account.save()
			
			next = request.POST.get('next')
			if not next: next = '/'
			return redirect(next)
		
	else:
		form = ChangeFirstTimePasswordForm()
	
	next = request.GET.get('next', '')
	return render_response(request, "registration/user_first_time_login.html", {'form':form, 'next':next})

def view_change_password(request):
	
	if request.method == 'POST':
		form = ChangePasswordForm(request.POST)
		if form.is_valid():
			username = form.cleaned_data['username']
			old_password = form.cleaned_data['old_password']
			new_password1 = form.cleaned_data['new_password1']
			new_password2 =form.cleaned_data['new_password2']
			
			user = User.objects.get(username=username)
			user.set_password(new_password1)
			user.save()
			
			return redirect('/accounts/login/')
		
	else:
		form = ChangePasswordForm()
	
	return render_response(request, "registration/user_change_password.html", {'form':form,})

#
# FRONTPAGE
#
@login_required
def view_frontpage(request):
	if request.user.is_superuser:
		return _view_admin_frontpage(request)
		
	else:
		primary_role = request.user.groups.all()[0] # Currently support only 1 role per user

		if primary_role.name == "sector_admin":
			return _view_sector_admin_frontpage(request)

		elif primary_role.name == "sector_manager":
			return _view_sector_manager_frontpage(request)

		elif primary_role.name == "sector_manager_assistant":
			return _view_sector_manager_assistant_frontpage(request)

		elif primary_role.name == "project_manager":
			return _view_project_manager_frontpage(request)

		elif primary_role.name == "project_manager_assistant":
			return _view_project_manager_assistant_frontpage(request)

def _view_admin_frontpage(request):
	return redirect("/administer/")

def _view_sector_admin_frontpage(request):
	return redirect("/sector/%d/" % request.user.get_profile().sector.id)

def _view_sector_manager_frontpage(request):
	return redirect("/sector/%d/" % request.user.get_profile().sector.id)

def _view_sector_manager_assistant_frontpage(request):
	responsibility = UserRoleResponsibility.objects.get(user=request.user.get_profile(), role__name="sector_manager_assistant")
	projects = responsibility.projects.all()
	for project in projects:
		project.reports = report_functions.get_submitted_and_overdue_reports(project)

		for report in project.reports:
			for schedule in report.schedules:
				schedule.comment_count = Comment.objects.filter(object_name='report', object_id=schedule.id).count()

	return render_response(request, "dashboard_sector_assistant.html", {'projects':projects})

def _view_project_manager_frontpage(request):
	responsibility = UserRoleResponsibility.objects.filter(user=request.user.get_profile(), role__name='project_manager')
	project = responsibility[0].projects.all()[0]
	return redirect("/project/%d/" % project.id)

def _view_project_manager_assistant_frontpage(request):
	responsibility = UserRoleResponsibility.objects.filter(user=request.user.get_profile(), role__name="project_manager_assistant")
	project = responsibility[0].projects.all()[0]
	return redirect("/project/%d/" % project.id)

@login_required
def view_dashboard_comments(request):
	user_account = request.user.get_profile()

	object_list = list()
	object_dict = dict()

	# Comments that the user has recieved.
	comments = CommentReceiver.objects.filter(receiver=request.user.get_profile(), is_read=False).order_by("-sent_on")
	for comment in comments:
		hash_str = "%s%d" % (comment.comment.object_name, comment.comment.object_id)
		if hash_str not in object_list:
			object = None

			if comment.comment.object_name == 'activity':
				object = Activity.objects.get(pk=comment.comment.object_id)

			elif comment.comment.object_name == 'project':
				object = Project.objects.get(pk=comment.comment.object_id)

			elif comment.comment.object_name == 'report':
				object = ReportSchedule.objects.get(pk=comment.comment.object_id)

			if object:
				object_list.append(hash_str)
				object_dict[hash_str] = {'comment':comment.comment, 'object':object, 'comments':[comment]}

		else:
			object_dict[hash_str]['comments'].append(comment)

	# Comments that the user has sent.
	#comments = Comment.objects.filter(sent_by_id=request.user.id)
	#for comment in comments:
	#	hash_str = "%s%d" % (comment.object_name, comment.object_id)
	#	if hash_str not in object_list:
	#		object = None

	#		if comment.object_name == 'activity':
	#			object = Activity.objects.get(pk=comment.object_id)

	#		elif comment.object_name == 'project':
	#			object = Project.objects.get(pk=comment.object_id)

	#		elif comment.object_name == 'report':
	#			object = ReportSchedule.objects.get(pk=comment.object_id)

	#		if object:
	#			object_list.append(hash_str)
	#			object_dict[hash_str] = {'comment':comment, 'object':object, 'comments':[comment]}

	#	else:
	#		object_dict[hash_str]['comments'].append(comment)

	objects = list()
	for object_hash in object_list:
		objects.append(object_dict[object_hash])

	return render_response(request, "dashboard_comments.html", {'objects':objects})

@login_required
def view_dashboard_comments_outbox(request):
	return render_response(request, "dashboard_comments_outbox.html", {'objects':objects})

@login_required
def view_dashboard_my_projects(request):
	
	if request.method == 'POST':
		projects = request.POST.getlist('project')
		
		responsibility = UserRoleResponsibility.objects.get(user=request.user.get_profile())
		
		for project_id in projects:
			project = Project.objects.get(pk=project_id)
			responsibility.projects.add(project)
		
		return redirect('view_frontpage')
		
	else:
		responsibility = UserRoleResponsibility.objects.get(user=request.user.get_profile())
		
		master_plans = MasterPlan.objects.filter(sector=request.user.get_profile().sector)
		
		for master_plan in master_plans:
			master_plan.projects = Project.objects.filter(master_plan=master_plan, parent_project=None)
			for project in master_plan.projects: project.responsible = _responsible_this_project(project, responsibility.projects.all())
		
		return render_response(request, "dashboard_sector_assistant_projects.html", {'master_plans':master_plans})

def _responsible_this_project(project, my_projects):
	for my_project in my_projects:
		if my_project.id == project.id:
			return True
	
	return False

#
# ADMIN
#
@login_required
def view_administer(request):
	return redirect('/administer/organization/')

@login_required
def view_administer_organization(request):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	sectors = Sector.objects.all().order_by('ref_no')
	for sector in sectors:
		sector.has_child = MasterPlan.objects.filter(sector=sector).count() > 0

	master_plans = MasterPlan.objects.all().order_by('ref_no')
	for master_plan in master_plans:
		master_plan.has_child = Plan.objects.filter(master_plan=master_plan).count() > 0 or Project.objects.filter(master_plan=master_plan).count()

		# Prepare year period
		year_period = master_plan.year_period
		master_plan.start = utilities.format_abbr_month_year(year_period.start)
		master_plan.end = utilities.format_abbr_month_year(year_period.end)

	return render_response(request, "administer_organization.html", {'sectors':sectors, 'master_plans':master_plans})

@login_required
def view_administer_organization_add_sector(request):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	if request.method == 'POST':
		form = SectorForm(request.POST)
		if form.is_valid():
			Sector.objects.create(ref_no=form.cleaned_data['ref_no'], name=form.cleaned_data['name'])

			return redirect('view_administer_organization')
	else:
		form = SectorForm()

	return render_response(request, "administer_organization_add_sector.html", {'form':form})

@login_required
def view_administer_organization_edit_sector(request, sector_id):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	sector = get_object_or_404(Sector, pk=sector_id)

	if request.method == 'POST':
		form = SectorForm(request.POST)
		if form.is_valid():
			sector.ref_no = form.cleaned_data['ref_no']
			sector.name = form.cleaned_data['name']
			sector.save()

			return redirect('view_administer_organization')

	else:
		form = SectorForm(initial={'ref_no':sector.ref_no, 'name':sector.name})

	return render_response(request, "administer_organization_edit_sector.html", {'form':form})

@login_required
def view_administer_organization_delete_sector(request, sector_id):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	sector = get_object_or_404(Sector, pk=sector_id)
	sector.delete()
	return redirect('view_administer_organization')

@login_required
def view_administer_organization_add_masterplan(request):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	if request.method == 'POST':
		form = MasterPlanForm(request.POST)
		if form.is_valid():
			ref_no = form.cleaned_data['ref_no']
			name = form.cleaned_data['name']
			sector = form.cleaned_data['sector']
			year_start = form.cleaned_data['year_start'] - 543
			year_end = form.cleaned_data['year_end'] - 543

			# Get default month period, we know that there's existing one.
			default_month_period = MasterPlanMonthPeriod.objects.get(is_default=True)

			year_period_start = date(year_start, default_month_period.start_month, 1)
			year_period_end = date(year_end, default_month_period.end_month, 1)
			year_period, created = MasterPlanYearPeriod.objects.get_or_create(start=year_period_start, end=year_period_end, month_period=default_month_period)

			MasterPlan.objects.create(sector=sector, ref_no=ref_no, name=name, year_period=year_period)

			return redirect('view_administer_organization')

	else:
		form = MasterPlanForm()

	return render_response(request, "administer_organization_add_masterplan.html", {'form':form})

@login_required
def view_administer_organization_edit_masterplan(request, master_plan_id):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)

	if request.method == 'POST':
		form = MasterPlanForm(request.POST)
		if form.is_valid():
			ref_no = form.cleaned_data['ref_no']
			name = form.cleaned_data['name']
			sector = form.cleaned_data['sector']
			year_start = form.cleaned_data['year_start'] - 543
			year_end = form.cleaned_data['year_end'] - 543

			# Get default month period, we know that there's existing one.
			default_month_period = MasterPlanMonthPeriod.objects.get(is_default=True)

			year_period_start = date(year_start, default_month_period.start_month, 1)
			year_period_end = date(year_end, default_month_period.end_month, 1)
			year_period, created = MasterPlanYearPeriod.objects.get_or_create(start=year_period_start, end=year_period_end, month_period=default_month_period)

			master_plan.sector = sector
			master_plan.ref_no = ref_no
			master_plan.name = name
			master_plan.year_period = year_period
			master_plan.save()

			return redirect('view_administer_organization')

	else:
		year_start = master_plan.year_period.start.year + 543
		year_end = master_plan.year_period.end.year + 543
		form = MasterPlanForm(initial={'sector':master_plan.sector.id, 'ref_no':master_plan.ref_no, 'name':master_plan.name, 'year_start':year_start, 'year_end':year_end})

	return render_response(request, "administer_organization_edit_masterplan.html", {'form':form})

@login_required
def view_administer_organization_delete_masterplan(request, master_plan_id):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)
	master_plan.delete()
	return redirect('view_administer_organization')

@login_required
def view_administer_users(request):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	users = User.objects.filter(is_superuser=False)
	for user in users:
		resps = UserRoleResponsibility.objects.filter(user=user.get_profile())

		projects = []
		roles = []
		for resp in resps:
			projects += [project.name for project in resp.projects.all()]
			group_name = GroupName.objects.get(group=resp.role)
			roles += [group_name.name]
		user.projects = ', '.join(projects)
		user.roles = ', '.join(roles)

	return render_response(request, "administer_users.html", {'users': users})

@login_required
def view_administer_users_add(request):
	if not request.user.is_superuser: return access_denied(request)
	
	if request.method == 'POST':
		form = UserAccountForm(request.POST)
		if form.is_valid():
			username = form.cleaned_data['username']
			email = form.cleaned_data['email']
			first_name = form.cleaned_data['first_name']
			last_name = form.cleaned_data['last_name']
			role = form.cleaned_data['role']
			sector = Sector(id=form.cleaned_data['sector'])
			responsible = form.cleaned_data['responsible']
			
			password = utilities.make_random_user_password()
			
			user = User.objects.create_user(username, email, password=password)
			user_account = UserAccount.objects.get(user=user)
			user_account.first_name = first_name
			user_account.last_name = last_name
			user_account.random_password = password
			user_account.sector = sector
			user_account.save()
			
			group = Group.objects.get(name=role)
			
			user.groups.add(group)
			responsibility = UserRoleResponsibility.objects.create(user=user_account, role=group)
			
			if role == 'project_manage' or role == 'project_manage_assistant':
				project = Project.objects.get(pk=responsible)
				responsibility.projects.add(project)
			else:
				responsibility.sectors.add(sector)
			
			return redirect('view_administer_users_password', user.id)
			
	else:
		form = UserAccountForm()
	
	if request.POST.get('responsible'):
		responsible = request.POST['responsible']
		project = Project.objects.get(pk=responsible)
		
		master_plans = MasterPlan.objects.all()
		projects = Project.objects.filter(master_plan=project.master_plan, parent_project=None)
		
		return render_response(request, "administer_users_modify.html", {'mode':'create', 'form': form, 'master_plans':master_plans, 'projects':projects, 'responsible':project})
	else:
		return render_response(request, "administer_users_modify.html", {'mode':'create', 'form': form, 'responsible':''})

@login_required
def view_administer_users_edit(request, user_id):
	if not request.user.is_superuser: return access_denied(request)
	user = User.objects.get(pk=user_id)
	
	if request.method == 'POST':
		form = UserAccountForm(request.POST)
		if form.is_valid():
			username = form.cleaned_data['username']
			email = form.cleaned_data['email']
			first_name = form.cleaned_data['first_name']
			last_name = form.cleaned_data['last_name']
			role = form.cleaned_data['role']
			sector = Sector(id=form.cleaned_data['sector'])
			responsible = form.cleaned_data['responsible']
			
			user.username = username
			user.email = email
			user.save()
			
			user_account = UserAccount.objects.get(user=user)
			user_account.first_name = first_name
			user_account.last_name = last_name
			user_account.sector = sector
			user_account.save()
			
			user_role = user.groups.all()[0]
			
			if role != user_role.name:
				group = Group.objects.get(name=role)
				user.groups.delete()
				user.groups.add(group)
				
				UserRoleResponsibility.objects.filter(user=user_account).delete()
				responsibility = UserRoleResponsibility.objects.create(user=user_account, role=group)
			
				if role == 'project_manage' or role == 'project_manage_assistant':
					project = Project.objects.get(pk=responsible)
					responsibility.projects.add(project)
				else:
					responsibility.sectors.add(sector)
			
			return redirect('view_administer_users_password', user.id)
		
		else:
			if request.POST.get('responsible'):
				responsible = request.POST['responsible']
				project = Project.objects.get(pk=responsible)
				
				master_plans = MasterPlan.objects.all()
				projects = Project.objects.filter(master_plan=project.master_plan, parent_project=None)
			else:
				project = None
				master_plans = None
				projects = None
		
	else:
		role = user.groups.all()[0].name
		if role == 'project_manager' or role == 'project_manager_assistant':
			responsible = UserRoleResponsibility.objects.filter(user=user.get_profile())[0].projects.all()[0].id
		else:
			responsible = None
		
		form = UserAccountForm(initial={\
			'username':user.username,\
			'email':user.email,\
			'first_name':user.get_profile().first_name,\
			'last_name':user.get_profile().last_name,\
			'role':role,\
			'sector':user.get_profile().sector,\
			'responsible':responsible});
		
		if responsible:
			project = Project.objects.get(pk=responsible)
			master_plans = MasterPlan.objects.all()
			projects = Project.objects.filter(master_plan=project.master_plan, parent_project=None)
		else:
			project = None
			master_plans = None
			projects = None
		
	return render_response(request, "administer_users_modify.html", {'mode':'edit', 'form': form, 'master_plans':master_plans, 'projects':projects, 'responsible':project})

@login_required
def view_administer_users_password(request, user_id):
	if not request.user.is_superuser: return access_denied(request)
	
	user = User.objects.get(pk=user_id)
	user_account = UserAccount.objects.get(user=user)
	
	return render_response(request, "administer_users_password.html", {'user_account': user_account})

@login_required
def view_administer_users_status(request, user_id):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)

	user = User.objects.get(pk=user_id)
	user.is_active = not user.is_active
	user.save()

	return HttpResponse(simplejson.dumps({'status': 'complete'}))

#
# SECTOR
#
@login_required
def view_sectors(request):
	sectors = Sector.objects.all().order_by('ref_no')
	current_date = date.today().replace(day=1)

	for sector in sectors:
		sector.master_plans = MasterPlan.objects.filter(sector=sector, year_period__start__lte=current_date, year_period__end__gte=current_date).order_by('ref_no')

	return render_response(request, "sectors_overview.html", {'sectors':sectors})

@login_required
def view_sector_overview(request, sector_id):
	sector = get_object_or_404(Sector, pk=sector_id)
	current_date = date.today()
	current_year = current_date.year

	master_plans = MasterPlan.objects.filter(sector=sector, year_period__start__lte=current_date, year_period__end__gte=current_date).order_by('ref_no')

	return render_response(request, "sector_overview.html", {'sector':sector, 'master_plans':master_plans,})

@login_required
def view_sector_reports(request, sector_id):
	sector = get_object_or_404(Sector, pk=sector_id)
	reports = Report.objects.filter(sector=sector).order_by('created')

	for report in reports:
		report.project_count = ReportProject.objects.filter(report=report).count()

	return render_response(request, "sector_reports.html", {'sector':sector, 'reports':reports})

@login_required
def view_sector_add_report(request, sector_id):
	sector = get_object_or_404(Sector, pk=sector_id)

	if request.method == 'POST':
		form = SectorReportForm(request.POST)
		if form.is_valid():
			report_name = form.cleaned_data['name']
			need_approval = form.cleaned_data['need_approval']
			schedule_cycle_length = form.cleaned_data['schedule_cycle_length']
			schedule_monthly_date = form.cleaned_data['schedule_monthly_date']

			Report.objects.create(name=report_name, need_approval=need_approval, need_checkup=True, schedule_cycle_length=schedule_cycle_length, schedule_monthly_date=schedule_monthly_date, sector=sector, created_by=request.user.get_profile())

			return redirect('view_sector_reports', (sector.id))

	else:
		form = SectorReportForm()

	return render_response(request, "sector_report_add.html", {'sector':sector, 'form':form})

@login_required
def view_sector_edit_report(request, sector_id, report_id):
	sector = get_object_or_404(Sector, pk=sector_id)
	report = get_object_or_404(Report, pk=report_id)

	if request.method == 'POST':
		form = SectorReportForm(request.POST)
		if form.is_valid():
			report.name = form.cleaned_data['name']
			report.need_approval = form.cleaned_data['need_approval']
			report.save()

			return redirect('view_sector_reports', (sector.id))

	else:
		form = SectorReportForm(initial={'name':report.name, 'need_approval':report.need_approval, 'schedule_cycle_length':report.schedule_cycle_length, 'schedule_monthly_date':report.schedule_monthly_date})

	return render_response(request, "sector_report_edit.html", {'sector':sector, 'form':form})

@login_required
def view_sector_delete_report(request, sector_id, report_id):
	sector = get_object_or_404(Sector, pk=sector_id)
	report = get_object_or_404(Report, pk=report_id)

	project_count = ReportProject.objects.filter(report=report).count()
	if not project_count: report.delete()

	return redirect('view_sector_reports', (sector.id))

#
# MASTER PLAN
#
@login_required
def view_master_plan_overview(request, master_plan_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)
	current_date = date.today()
	current_year = utilities.current_year_number()

	# Plans
	plans = Plan.objects.filter(master_plan=master_plan)
	for plan in plans:
		plan.current_projects = Project.objects.filter(plan=plan, start_date__lte=current_date, end_date__gte=current_date)

	master_plan.plans = plans

	return render_response(request, "master_plan_overview.html", {'master_plan':master_plan, 'current_year':current_year})

@login_required
def view_master_plan_plans(request, master_plan_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)

	plans = Plan.objects.filter(master_plan=master_plan)

	for plan in plans:
		plan.projects = Project.objects.filter(plan=plan).order_by('-start_date')

	return render_response(request, "master_plan_plans.html", {'master_plan':master_plan, 'plans':plans})

@login_required
def view_master_plan_organization(request, master_plan_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)

	plans = Plan.objects.filter(master_plan=master_plan)

	for plan in plans:
		plan.projects = Project.objects.filter(plan=plan).order_by('-start_date')
		for project in plan.projects:
			if Project.objects.filter(parent_project=project).count():
				project.has_child = True

	return render_response(request, "master_plan_organization.html", {'master_plan':master_plan, 'plans':plans})

@login_required
def view_master_plan_add_plan(request, master_plan_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)
	if request.method == 'POST':
		form = PlanForm(request.POST)
		if form.is_valid():
			cleaned_data = form.cleaned_data
			plan = Plan.objects.create(ref_no=cleaned_data['ref_no'], name=cleaned_data['name'], master_plan=master_plan)
			set_message(request, u"เพิ่ม %s แล้ว" % plan.name)

			return redirect('view_master_plan_organization', (master_plan_id))
	else:
		form = PlanForm()

	return render_response(request, "master_plan_add_plan.html", {'master_plan':master_plan, 'form':form})

@login_required
def view_master_plan_edit_plan(request, master_plan_id, plan_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)
	plan = get_object_or_404(Plan, pk=plan_id)

	if request.method == 'POST':
		form = PlanForm(request.POST)
		if form.is_valid():
			cleaned_data = form.cleaned_data
			plan.ref_no = cleaned_data['ref_no']
			plan.name = cleaned_data['name']
			plan.save()

			set_message(request, u"บันทึกการเปลี่ยนแปลงของ %s แล้ว" % plan.name)

			return redirect('view_master_plan_organization', (master_plan_id))
	else:
		form = PlanForm(initial={'ref_no':plan.ref_no, 'name':plan.name})

	return render_response(request, "master_plan_edit_plan.html", {'master_plan':master_plan, 'form':form})

@login_required
def view_master_plan_delete_plan(request, master_plan_id, plan_id):
	plan = get_object_or_404(Plan, pk=plan_id)
	plan.delete()
	set_message(request, u"กลุ่มแผนงาน <em>%s</em> ถูกลบแล้ว" % plan.name)

	return redirect('view_master_plan_organization', (master_plan_id))

@login_required
def view_master_plan_add_project(request, master_plan_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)

	return render_response(request, "master_plan_add_project.html", {'master_plan':master_plan, })

@login_required
def view_master_plan_edit_project(request, master_plan_id, project_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)

	return render_response(request, "master_plan_edit_project.html", {'master_plan':master_plan, })

@login_required
def view_master_plan_delete_project(request, master_plan_id, project_id):

	pass

#
# PROJECT
#
@login_required
def view_project_overview(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	current_date = date.today()

	if not project.parent_project:
		current_projects = Project.objects.filter(parent_project=project, start_date__lte=current_date, end_date__gte=current_date)

		report_schedules = ReportSchedule.objects.filter(report_project__project=project).filter(Q(state=APPROVE_ACTIVITY) | (Q(state=SUBMIT_ACTIVITY) & Q(report_project__report__need_approval=False)) | (Q(state=SUBMIT_ACTIVITY) & Q(report_project__report__need_checkup=False))).order_by('-due_date')[:5]

		return render_response(request, "project_overview.html", {'project':project, 'current_projects':current_projects, 'report_schedules':report_schedules})

	else:
		current_activities = Activity.objects.filter(project=project, start_date__lte=current_date, end_date__gte=current_date)

		return render_response(request, "project_overview.html", {'project':project, 'current_activities':current_activities})

@login_required
def view_project_projects(request, project_id):
	project = get_object_or_404(Project, pk=project_id)

	projects = Project.objects.filter(parent_project=project).order_by('-start_date')

	return render_response(request, "project_projects.html", {'project':project, 'projects':projects})

@login_required
def view_project_add(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	
	if utilities.responsible(request.user, ('project_manager','project_manager_assistant'), project):
		if request.method == "POST":
			form = ProjectForm(request.POST)
			if form.is_valid():
				created_project = Project.objects.create(
					sector=project.sector, 
					master_plan=project.master_plan, 
					parent_project=project, 
					prefix_name=Project.PROJECT_IS_PROJECT, 
					ref_no=form.cleaned_data['ref_no'],
					name=form.cleaned_data['name'],
					start_date=form.cleaned_data['start_date'],
					end_date=form.cleaned_data['end_date']
				)
				
				return redirect('view_project_overview', (created_project.id))
	
		else:
			form = ProjectForm()
	
		return render_response(request, "project_projects_add.html", {'project':project, 'form':form})
	
	else:
		return redirect('view_project_projects', (project.id))

@login_required
def view_project_edit(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	head_project = project.parent_project if project.parent_project else project
	
	if utilities.responsible(request.user, ('project_manager','project_manager_assistant'), head_project):
		if request.method == "POST":
			form = ProjectForm(request.POST)
			if form.is_valid():
				project.ref_no = form.cleaned_data.get('ref_no')
				project.name = form.cleaned_data.get('name')
				project.description = form.cleaned_data.get('description', '')
				project.start_date = form.cleaned_data.get('start_date')
				project.end_date = form.cleaned_data.get('end_date')
				project.save()
				
				return redirect('view_project_overview', (project.id))
	
		else:
			form = ProjectForm(project.__dict__)

		return render_response(request, "project_projects_edit.html", {'project':project, 'form':form})
	
	else:
		return redirect('view_project_projects', (project.id))

@login_required
def view_project_delete(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	head_project = project.parent_project if project.parent_project else project
	
	if utilities.responsible(request.user, ('project_manager','project_manager_assistant'), head_project):
		if Activity.objects.filter(project=project).count():
			set_message(request, 'ยังมีกิจกรรมอยู่ภายใต้โครงการ ต้องลบกิจกรรมก่อนลบโครงการ')
			return redirect('view_project_overview', (project.id))
		else:
			project.delete()
			return redirect('view_project_projects', (head_project.id))
	
	else:
		return redirect('view_project_projects', (head_project.id))

@login_required
def view_project_reports(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	
	report_projects = ReportProject.objects.filter(project=project)
	
	for report_project in report_projects:
		report_project.schedules = ReportSchedule.objects.filter(report_project=report_project).filter(Q(state=APPROVE_ACTIVITY) | (Q(state=SUBMIT_ACTIVITY) & Q(report_project__report__need_approval=False)) | (Q(state=SUBMIT_ACTIVITY) & Q(report_project__report__need_checkup=False))).order_by('-due_date')
		
		year_list = set()
		for schedule in report_project.schedules: year_list.add(schedule.due_date.year)
		year_list = sorted(year_list, reverse=True)
		
		report_project.year_list = year_list
	
	return render_response(request, "project_reports.html", {'project':project, 'report_projects':report_projects})

@login_required
def view_project_reports_list(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	
	if not utilities.responsible(request.user, ('project_manager','project_manager_assistant'), project):
		return redirect('view_project_reports', (project.id))
	
	report_projects = ReportProject.objects.filter(project=project)

	sector_reports = list()
	project_reports = list()

	for report_project in report_projects:
		if report_project.report.sector:
			sector_reports.append(report_project.report)
		else:
			project_reports.append(report_project.report)

	return render_response(request, "project_reports_list.html", {'project':project, 'sector_reports':sector_reports, 'project_reports':project_reports})

@login_required
def view_project_reports_add(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	
	if not utilities.responsible(request.user, ('project_manager','project_manager_assistant'), project):
		return redirect('view_project_reports', (project.id))
	
	if request.method == 'POST':
		form = AddProjectReportForm(request.POST)
		if form.is_valid():
			name = form.cleaned_data['name']
			need_checkup = form.cleaned_data['need_checkup']
			need_approval = form.cleaned_data['need_approval']
			schedule_cycle_length = form.cleaned_data['schedule_cycle_length']
			schedule_monthly_date = form.cleaned_data['schedule_monthly_date']
			start_date = form.cleaned_data['start_date']
			end_date = form.cleaned_data['end_date']
			
			# TODO
		
	else:
		form = AddProjectReportForm()

	return render_response(request, "project_reports_add.html", {'project':project, 'form':form})

@login_required
def view_project_report_edit(request, project_id, report_id):
	project = get_object_or_404(Project, pk=project_id)
	report = get_object_or_404(Report, pk=report_id)
	
	if not utilities.responsible(request.user, ('project_manager','project_manager_assistant'), project):
		return redirect('view_project_reports', (project.id))
	
	if request.method == 'POST':
		form = EditProjectReportForm(request.POST)
		if form.is_valid():
			name = form.cleaned_data['name']
			
			report.name = name
			report.save()
		
	else:
		form = EditProjectReportForm(initial={})

	return render_response(request, "project_reports_edit.html", {'project':project, 'form':form})

@login_required
def view_project_reports_send(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	reports = report_functions.get_nextdue_and_overdue_reports(project_id)
	
	if not utilities.responsible(request.user, ('project_manager','project_manager_assistant'), project):
		return redirect('view_project_reports', (project.id))
	
	for report in reports:
		for schedule in report.schedules:
			schedule.comment_count = Comment.objects.filter(object_name='report', object_id=schedule.id).count()

	return render_response(request, "project_reports_send.html", {'project':project, 'reports':reports})

@login_required
def view_project_comments(request, project_id):
	project = get_object_or_404(Project, pk=project_id)

	comments = CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='project', \
		comment__object_id=project.id).order_by("-sent_on")

	for comment in comments:
		comment.receivers = CommentReceiver.objects.filter(comment=comment.comment)
		comment.already_read = comment.is_read

	CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='project', \
		comment__object_id=project.id).update(is_read=True)

	return render_response(request, "project_comments.html", {'project':project, 'comments':comments})

# Helper function to find previous and next month.
def prev_month(year, month, num=1):
	'''Return (year, month)'''
	MONTH = range(1, 13)
	month_index = MONTH.index(month)
	prev_index = month_index - num
	if abs(prev_index) > 12:
		prev_index = 12 % prev_index

	if prev_index < 0:
		year = year + (prev_index / 12)

	return (year, MONTH[prev_index])

def next_month(year, month, num=1):
	'''Return (year, month)'''
	MONTH = range(1, 13)
	delta = num
	index = month + num

	return (year + (index / 13), MONTH[index % 12 - 1])

@login_required
def view_project_activities(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	current_date = date.today()

	activities = Activity.objects.filter(project=project).order_by('-start_date')

	# Find activities in past month, current month and next month.
	num = 3
	prev_month_ = prev_month(current_date.year, current_date.month, num)
	start = date(*prev_month_, day=1)
	next_month_ = next_month(current_date.year, current_date.month, num)
	end = date(*next_month_, day=calendar.monthrange(*next_month_)[1])

	prev_month_ = "%04d%02d" % prev_month(current_date.year, current_date.month)
	next_month_ = "%04d%02d" % next_month(current_date.year, current_date.month)

	recent_activities = Activity.objects.filter(project=project).filter( \
		Q(start_date__lte=start) & Q(end_date__gte=end) | \
		Q(start_date__lte=end) & Q(start_date__gte=start) | \
		Q(end_date__lte=end) & Q(end_date__gte=start))

	return render_response(request, "project_activities.html", {'project':project, 'activities':activities, 'recent_activities':recent_activities,'prev_month':prev_month_,'next_month':next_month_})

@login_required
def view_project_activities_ajax(request, project_id, yearmonth):
	project = get_object_or_404(Project, pk=project_id)

	year = int(yearmonth[:4])
	month = int(yearmonth[4:])

	# Find activities in past month, current month and future month.
	num = 3
	prev_month_ = prev_month(year, month, num)
	next_month_ = next_month(year, month, num)

	start = date(*prev_month_, day=1)
	end = date(*next_month_, day=calendar.monthrange(*next_month_)[1])

	prev_month_ = "%04d%02d" % prev_month(year, month)
	next_month_ = "%04d%02d" % next_month(year, month)

	recent_activities = Activity.objects.filter(project=project).filter( \
		Q(start_date__lte=start) & Q(end_date__gte=end) | \
		Q(start_date__lte=end) & Q(start_date__gte=start) | \
		Q(end_date__lte=end) & Q(end_date__gte=start))

	return render_response(request, "project_activities_ajax.html", {'recent_activities':recent_activities,'prev_month':prev_month_,'next_month':next_month_})

@login_required
def view_activity_add(request, project_id):
	project = get_object_or_404(Project, pk=project_id)

	head_project = project.parent_project if project.parent_project else project

	if utilities.responsible(request.user, ('project_manager','project_manager_assistant'), head_project):
		if request.method == "POST":
			form = ActivityForm(request.POST)
			if form.is_valid():
				activity = Activity()

				activity.project     = project
				activity.name        = form.cleaned_data['name']
				activity.start_date  = form.cleaned_data['start_date']
				activity.end_date    = form.cleaned_data['end_date']
				activity.description = form.cleaned_data['description']
				activity.location    = form.cleaned_data['location']
				activity.result_goal = form.cleaned_data['result_goal']
				activity.result_real = form.cleaned_data['result_real']
				activity.save()

				return redirect('view_activity_overview', (activity.id))

		else:
			form = ActivityForm()
		
		return render_response(request, "project_activity_add.html", {'project':project, 'form':form})
		
	else:
		return redirect('view_project_activities', (project.id))

@login_required
def view_activity_edit(request, activity_id):
	activity = get_object_or_404(Activity, pk=activity_id)
	project = activity.project

	head_project = project.parent_project if project.parent_project else project

	if utilities.responsible(request.user, ('project_manager','project_manager_assistant'), head_project):
		if request.method == 'POST':
			form = ActivityForm(request.POST)
			if form.is_valid():
				activity.name        = form.cleaned_data['name']
				activity.start_date  = form.cleaned_data['start_date']
				activity.end_date    = form.cleaned_data['end_date']
				activity.description = form.cleaned_data['description']
				activity.location    = form.cleaned_data['location']
				activity.result_goal = form.cleaned_data['result_goal']
				activity.result_real = form.cleaned_data['result_real']
				activity.save()

				return redirect('view_activity_overview', (activity.id))
		else:
			form = ActivityForm(activity.__dict__)
		
		return render_response(request, "project_activity_edit.html", {'activity':activity, 'form':form})
	
	else:
		return redirect('view_activity_overview', (activity.id))

@login_required
def view_activity_delete(request, activity_id):
	activity = Activity.objects.get(pk=activity_id)
	project = activity.project

	head_project = project.parent_project if project.parent_project else project

	if utilities.responsible(request.user, ('project_manager','project_manager_assistant'), head_project):
		activity.delete()
		set_message(request, 'ลบกิจกรรมเรียบร้อย')

	return redirect("/project/%d/activities/" % project.id)

@login_required
def view_project_comments(request, project_id):
	project = get_object_or_404(Project, pk=project_id)

	comments = CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='project', \
		comment__object_id=project_id).order_by("-sent_on")

	for comment in comments:
		comment.receivers = CommentReceiver.objects.filter(comment=comment.comment)
		comment.already_read = comment.is_read

	CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='project', \
		comment__object_id=project_id).update(is_read=True)

	return render_response(request, "project_comments.html", {'project':project, 'comments':comments})

#
# ACTIVITY
#

@login_required
def view_activity_overview(request, activity_id):
	activity = get_object_or_404(Activity, pk=activity_id)
	return render_response(request, "activity_overview.html", {'activity':activity,})

@login_required
def view_activity_comments(request, activity_id):
	activity = get_object_or_404(Activity, pk=activity_id)

	comments = CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='activity', \
		comment__object_id=activity_id).order_by("-sent_on")

	for comment in comments:
		comment.receivers = CommentReceiver.objects.filter(comment=comment.comment)
		comment.already_read = comment.is_read

	CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='activity', \
		comment__object_id=activity_id).update(is_read=True)

	return render_response(request, "activity_comments.html", {'activity':activity, 'comments':comments,})

#
# REPORT
#

@login_required
def view_report_overview(request, report_id):
	report_schedule = get_object_or_404(ReportSchedule, pk=report_id)

	if request.method == 'POST':
		project = report_schedule.report_project.report.project
		
		if not utilities.responsible(request.user, ('project_manager','project_manager_assistant'), project):
			return redirect('view_project_reports', (project.id))
		
		submit_type = request.POST.get('submit')

		if submit_type == 'submit-file':
			schedule_id = request.POST.get("schedule_id")
			schedule = ReportSchedule.objects.get(pk=schedule_id)

			file_response = ReportScheduleFileResponse.objects.create(schedule=schedule, uploaded_by=request.user.get_profile())

			# Uploading directory
			uploading_directory = "%s/%d/" % (settings.REPORT_SUBMIT_FILE_PATH, schedule.id)
			if not os.path.exists(uploading_directory): os.makedirs(uploading_directory)

			# Uploading file
			uploading_file = request.FILES['uploading_file']
			(file_name, separator, file_ext) = uploading_file.name.rpartition('.')

			unique_filename = '%s.%s' % (file_name, file_ext)
			if os.path.isfile('%s%s' % (uploading_directory, unique_filename)):
				# Duplicated filename
				suffix_counter = 1

				while os.path.isfile('%s%s(%d).%s' % (uploading_directory, file_name, suffix_counter, file_ext)):
					suffix_counter = suffix_counter + 1

				unique_filename = '%s(%d).%s' % (file_name, suffix_counter, file_ext)

			file_response.filename = unique_filename
			file_response.save()

			destination = open(uploading_directory + unique_filename, 'wb')
			for chunk in request.FILES['uploading_file'].chunks(): destination.write(chunk)
			destination.close()

		elif submit_type == 'submit-text':
			schedule_id = request.POST.get("schedule_id")
			schedule = ReportSchedule.objects.get(pk=schedule_id)

			text = request.POST.get("text")

			try:
				text_response = ReportScheduleTextResponse.objects.get(schedule=schedule)

			except ReportScheduleTextResponse.DoesNotExist:
				text_response = ReportScheduleTextResponse.objects.create(schedule=schedule, submitted_by=request.user.get_profile())

			text_response.text = text
			text_response.save()

		elif submit_type == 'submit-report':
			schedule_id = request.POST.get("schedule_id")
			schedule = ReportSchedule.objects.get(pk=schedule_id)

			schedule.state = SUBMIT_ACTIVITY
			schedule.submitted_on = datetime.now()
			schedule.approval_on = None
			schedule.save()

		return redirect('/report/%d/' % schedule.id)

	current_date = date.today()

	if report_schedule.state == NO_ACTIVITY and report_schedule.due_date < current_date:
		report_schedule.status_code = 'overdue'
	elif report_schedule.state == NO_ACTIVITY:
		report_schedule.status_code = 'not_submitted'
	elif report_schedule.state == SUBMIT_ACTIVITY and not report_schedule.report_project.report.need_approval:
		report_schedule.status_code = 'submitted'
	elif report_schedule.state == SUBMIT_ACTIVITY and report_schedule.report_project.report.need_approval:
		report_schedule.status_code = 'waiting'
	elif report_schedule.state == APPROVE_ACTIVITY:
		report_schedule.status_code = 'approved'
	elif report_schedule.state == APPROVE_ACTIVITY:
		report_schedule.status_code = 'rejected'

	report_schedule.allow_modifying = report_schedule.status_code in ('overdue', 'not_submitted', 'rejected')

	try:
		report_schedule.text_response = ReportScheduleTextResponse.objects.get(schedule=report_schedule)
	except ReportScheduleTextResponse.DoesNotExist:
		report_schedule.text_response = ''

	report_schedule.files = ReportScheduleFileResponse.objects.filter(schedule=report_schedule)

	return render_response(request, "report_overview.html", {'report_schedule':report_schedule, 'REPORT_SUBMIT_FILE_URL':settings.REPORT_SUBMIT_FILE_URL, })

@login_required
def view_report_comments(request, report_id):
	report = get_object_or_404(ReportSchedule, pk=report_id)
	
	comments = CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='report', \
		comment__object_id=report.id).order_by("-sent_on")

	for comment in comments:
		comment.receivers = CommentReceiver.objects.filter(comment=comment.comment)
		comment.already_read = comment.is_read

	CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='report', \
		comment__object_id=report.id).update(is_read=True)

	return render_response(request, "report_comments.html", {'report_schedule':report, 'comments':comments, })
