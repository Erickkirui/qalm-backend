from flask import Blueprint
from flask_restful import Api

from Server.Views.Users import (
    AddUser,
    Login,
    GetAllUsers,
    UserResource
)

from Server.Views.TherapistViews import (
    RegisterTherapist,
    ApproveTherapist,
    GetAllTherapists,
    GetPendingTherapists,
    TherapistResource,
)



from Server.Views.JournalViews import (
    CreateJournal,
    GetMyJournals,
    JournalResource,
)


from Server.Views.TherapistMatchPreferenceViews import (
    TherapistMatchPreferenceResource,
)



from Server.Views.AppointmentViews import (
    CreateAppointment,
    MyAppointments,
    AppointmentResource,
    ConfirmAppointment,
    RejectAppointment,
    CancelAppointment,
    CompleteAppointment,
    MarkAppointmentNoShow,
    UpdateAppointmentPayment,
    AdminAppointments,
)



Version_one = Blueprint('auth', __name__, url_prefix='/api/qalm')
api = Api(Version_one)


#User 
api.add_resource(AddUser, "/users")
api.add_resource(Login, "/login")
api.add_resource(GetAllUsers, "/users/all")
api.add_resource(UserResource, "/users/<int:user_id>")

#Therapist
api.add_resource(RegisterTherapist, "/therapists/register")
api.add_resource(GetAllTherapists, "/therapists")
api.add_resource(GetPendingTherapists, "/therapists/pending")
api.add_resource(ApproveTherapist, "/therapists/<int:therapist_id>/approval")
api.add_resource(TherapistResource, "/therapists/<int:therapist_id>")


#journal
api.add_resource(CreateJournal, "/journals")
api.add_resource(GetMyJournals, "/journals")
api.add_resource(JournalResource, "/journals/<int:journal_id>")


# appointment
api.add_resource(CreateAppointment, "/appointments")
api.add_resource(MyAppointments, "/appointments")
api.add_resource(AppointmentResource, "/appointments/<int:appointment_id>")
api.add_resource(ConfirmAppointment, "/appointments/<int:appointment_id>/confirm")
api.add_resource(RejectAppointment, "/appointments/<int:appointment_id>/reject")
api.add_resource(CancelAppointment, "/appointments/<int:appointment_id>/cancel")
api.add_resource(CompleteAppointment, "/appointments/<int:appointment_id>/complete")
api.add_resource(MarkAppointmentNoShow, "/appointments/<int:appointment_id>/no-show")
api.add_resource(UpdateAppointmentPayment, "/appointments/<int:appointment_id>/payment")
api.add_resource(AdminAppointments, "/appointments/admin")


#matching 
api.add_resource(TherapistMatchPreferenceResource, "/therapist-match-preferences")


