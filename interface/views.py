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
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

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
	manager = UserRoleResponsibility.objects.filter(user=request.user.get_profile(), role__name='project_manager')
	project = manager[0].projects.all()[0]
	return redirect("/project/%d/" % project.id)

def _view_project_manager_assistant_frontpage(request):
	responsibility = UserRoleResponsibility.objects.get(user=request.user.get_profile(), role__name="project_manager_assistant")
	project = manager[0].projects.all()[0]
	return redirect("/project/%d/" % project.id)

@login_required
def view_dashboard_comments(request):
	user_account = request.user.get_profile()

	comments = CommentReceiver.objects.filter(receiver=request.user.get_profile(), is_read=False).order_by("-sent_on")

	object_list = list()
	object_dict = dict()

	for comment in comments:
		hash_str = "%s%d" % (comment.comment.object_name, comment.comment.object_id)
		if hash_str not in object_list:
			object = None

			if comment.comment.object_name == "activity":
				object = Activity.objects.get(pk=comment.comment.object_id)

			elif comment.comment.object_name == "project" or comment.comment.object_name == "program":
				object = Project.objects.get(pk=comment.comment.object_id)

			elif comment.comment.object_name == "report":
				object = ReportSchedule.objects.get(pk=comment.comment.object_id)

			if object:
				object_list.append(hash_str)
				object_dict[hash_str] = {'comment':comment.comment, 'object':object, 'comments':[comment]}

		else:
			object_dict[hash_str]['comments'].append(comment)

	objects = list()
	for object_hash in object_list:
		objects.append(object_dict[object_hash])

	return render_response(request, "dashboard_comments.html", {'objects':objects})

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
	
	return render_response(request, "administer_organization.html", {})

@login_required
def view_administer_users(request):
	user_account = request.user.get_profile()
	if not request.user.is_superuser: return access_denied(request)
	
	return render_response(request, "administer_users.html", {})

#
# SECTOR
#
@login_required
def view_sectors(request):
	sectors = Sector.objects.all().order_by('ref_no')

	for sector in sectors:
		sector.master_plans = MasterPlan.objects.filter(sector=sector, is_active=True).order_by('ref_no')

	return render_response(request, "sectors_overview.html", {'sectors':sectors})
	
@login_required
def view_sector_overview(request, sector_id):
	sector = get_object_or_404(Sector, pk=sector_id)
	current_date = date.today()
	current_year = current_date.year
	
	master_plans = MasterPlan.objects.filter(sector=sector, is_active=True, start_year__lte=current_year, end_year__gte=current_year).order_by('ref_no')
	
	return render_response(request, "sector_overview.html", {'sector':sector, 'master_plans':master_plans,})

@login_required
def view_sector_master_plans(request, sector_id):
	sector = get_object_or_404(Sector, pk=sector_id)
	current_date = date.today()

	master_plans = MasterPlan.objects.filter(sector=sector, is_active=True)

	for master_plan in master_plans:
		master_plan.plans = Plan.objects.filter(master_plan=master_plan)

		for plan in master_plan.plans:
			plan.current_projects = Project.objects.filter(plan=plan, start_date__lte=current_date, end_date__gte=current_date)
			plan.future_projects = Project.objects.filter(plan=plan, start_date__gt=current_date)
			plan.past_projects = Project.objects.filter(plan=plan, end_date__lt=current_date)

		master_plan.projects = Project.objects.filter(master_plan=master_plan, plan=None, parent_project=None)

	return render_response(request, "sector_master_plans.html", {'sector':sector, 'master_plans':master_plans})

#
# MASTER PLAN
#
@login_required
def view_master_plan_overview(request, master_plan_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)
	current_date = date.today()
	current_year = utilities.what_is_current_year(master_plan)
	
	master_plan.years = range(master_plan.start_year, master_plan.end_year+1)
	
	# Plans
	plans = Plan.objects.filter(master_plan=master_plan)
	for plan in plans:
		plan.current_projects = Project.objects.filter(plan=plan, start_date__lte=current_date, end_date__gte=current_date)
		
	master_plan.plans = plans
	
	return render_response(request, "master_plan_overview.html", {'master_plan':master_plan, 'current_year':current_year})

@login_required
def view_master_plan_plans(request, master_plan_id):
	master_plan = get_object_or_404(MasterPlan, pk=master_plan_id)
	current_date = date.today()

	plans = Plan.objects.filter(master_plan=master_plan)

	for plan in plans:
		plan.current_projects = Project.objects.filter(plan=plan, start_date__lte=current_date, end_date__gte=current_date)
		plan.future_projects = Project.objects.filter(plan=plan, start_date__gt=current_date)
		plan.past_projects = Project.objects.filter(plan=plan, end_date__lt=current_date)
		
		plan.unscheduled_projects = Project.objects.filter(plan=plan, start_date=None, end_date=None)
	
	return render_response(request, "master_plan_plans.html", {'master_plan':master_plan, 'plans':plans})

#
# PROJECT
#
@login_required
def view_project_overview(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	current_date = date.today()
	
	if not project.parent_project:
		current_projects = Project.objects.filter(parent_project=project, start_date__lte=current_date, end_date__gte=current_date)
	
	else:
		pass # Find current activities
	
	report_schedules = ReportSchedule.objects.filter(report_project__project=project).filter(Q(state=APPROVE_ACTIVITY) | (Q(state=SUBMIT_ACTIVITY) and Q(report_project__report__need_approval=False)) | (Q(state=SUBMIT_ACTIVITY) and Q(report_project__report__need_checkup=False))).order_by('-due_date')[:5]
	
	return render_response(request, "project_overview.html", {'project':project, 'current_projects':current_projects, 'report_schedules':report_schedules})

@login_required
def view_project_projects(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	
	projects = Project.objects.filter(parent_project=project).order_by('-start_date')

	return render_response(request, "project_projects.html", {'project':project, 'projects':projects})

@login_required
def view_project_add(request, project_id):
	pass

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
def view_project_reports_add(request, project_id):
	
	pass

@login_required
def view_project_reports_send(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	reports = report_functions.get_nextdue_and_overdue_reports(project_id)
	
	for report in reports:
		for schedule in report.schedules:
			schedule.comment_count = Comment.objects.filter(object_name='report', object_id=schedule.id).count()

	return render_response(request, "project_reports_send.html", {'project':project, 'reports':reports})

@login_required
def view_program_comments(request, program_id):
	program = get_object_or_404(Project, pk=program_id)

	comments = CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='program', \
		comment__object_id=program_id).order_by("-sent_on")

	for comment in comments:
		comment.receivers = CommentReceiver.objects.filter(comment=comment.comment)
		comment.already_read = comment.is_read

	CommentReceiver.objects.filter(receiver=request.user.get_profile(), comment__object_name='program', \
		comment__object_id=program_id).update(is_read=True)
	
	return render_response(request, "project_comments.html", {'project':program, 'comments':comments})

#
# PROJECT
#
#@login_required
#def view_project_overview(request, project_id):
#	current_date = date.today()
#	project = get_object_or_404(Project, pk=project_id)
#
#	report_projects = ReportProject.objects.filter(project=project)
#	report_schedules = ReportSchedule.objects.filter(report_project__in=report_projects, is_submitted=True, last_activity=APPROVE_ACTIVITY).order_by('-due_date')
#	
#	current_activities = project.activity_set.filter(start_date__lte=current_date, end_date__gte=current_date).order_by('end_date')
#	future_activities = project.activity_set.filter(start_date__gt=current_date).order_by('start_date')
#	return render_response(request, "project_overview.html", {'project':project, 'current_activities':current_activities, 'future_activities':future_activities, 'report_schedules':report_schedules})

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
	current_activities = Activity.objects.filter(project=project, start_date__lte=current_date, end_date__gte=current_date)
	future_activities = Activity.objects.filter(project=project, start_date__gt=current_date)
	past_activities = Activity.objects.filter(project=project, end_date__lt=current_date)

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

	return render_response(request, "project_activities.html", {'project':project, 'current_activities':current_activities, 'future_activities':future_activities, 'past_activities':past_activities,'recent_activities':recent_activities,'prev_month':prev_month_,'next_month':next_month_})

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

"""
@login_required
def view_project_reports(request, project_id):
	project = get_object_or_404(Project, pk=project_id)

	return render_response(request, "project_reports.html", {'project':project})

@login_required
def view_project_reports_send(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	reports = report_functions.get_nextdue_and_overdue_reports(project_id)

	for report in reports:
		for schedule in report.schedules:
			schedule.files = ReportScheduleFileResponse.objects.filter(schedule=schedule)

	return render_response(request, "project_reports_send.html", {'project':project, 'reports':reports, 'REPORT_SUBMIT_FILE_URL':settings.REPORT_SUBMIT_FILE_URL})
"""
@login_required
def view_activity_add(request, project_id):
	project = get_object_or_404(Project, pk=project_id)
	message = ''
	if request.method == "POST":
		form = AddActivityForm(request.POST)
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

			utilities.set_message(request, 'Your activity has been create.')

			return redirect("/activity/%d/" % activity.id)

	else:
		form = AddActivityForm()

	return render_response(request, "project_activity_add.html", {'project':project, 'form':form, 'message': message})

@login_required
def view_activity_edit(request, activity_id):
	activity = Activity.objects.get(pk=activity_id)
	project = activity.project

	if request.method == "POST":
		form = AddActivityForm(request.POST)
		if form.is_valid():
			activity.name        = form.cleaned_data['name']
			activity.start_date  = form.cleaned_data['start_date']
			activity.end_date    = form.cleaned_data['end_date']
			activity.description = form.cleaned_data['description']
			activity.location    = form.cleaned_data['location']
			activity.result_goal = form.cleaned_data['result_goal']
			activity.result_real = form.cleaned_data['result_real']
			activity.save()

			set_message(request, 'Your activity has been update.')

			return redirect("/activity/%d/" % activity.id)

	form = AddActivityForm(activity.__dict__)
	return render_response(request, "project_activity_edit.html", {'project':project, 'form':form})

@login_required
def view_activity_delete(request, activity_id):
	activity = Activity.objects.get(pk=activity_id)
	project = activity.project
	activity.delete()

	set_message(request, 'Your activity has been delete.')

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
def view_activity_pictures(request, activity_id):
	activity = get_object_or_404(Activity, pk=activity_id)

	return render_response(request, "activity_pictures.html", {'activity':activity, })

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
	
	print report_schedule.files
	
	return render_response(request, "report_overview.html", {'report_schedule':report_schedule, 'REPORT_SUBMIT_FILE_URL':settings.REPORT_SUBMIT_FILE_URL, })

@login_required
def view_report_comments(request, report_id):
	report_schedule = get_object_or_404(ReportSchedule, pk=report_id)

	comments = Comment.objects.filter(object_name="report", object_id=report_id).order_by("-sent_on")

	return render_response(request, "report_comments.html", {'report_schedule':report_schedule, 'comments':comments, })
