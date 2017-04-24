# http://www.chrisumbel.com/article/windows_services_in_python
import win32service
import win32serviceutil
import win32event


class PySvc(win32serviceutil.ServiceFramework):
    # you can NET START/STOP the service by the following name
    _svc_name_ = "TeamworkSvc"
    # this text shows up as the service name in the Service
    # Control Manager (SCM)
    _svc_display_name_ = "Teamwork-Shopify Service"
    # this text shows up as the description in the SCM
    _svc_description_ = "This service gets data from Teamwork API and sends them to Shopify API"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # create an event to listen for stop requests on
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    # core logic of the service
    def SvcDoRun(self):
        import servicemanager
        import sys
        import os
        import teamworker
        import shopifier
        import utils

        utils.mkdirs()
        fn = os.path.join(utils._DIR, 'log', utils.time_str() + '.log')
        f = open(fn, 'w')
        sys.stdout = f

        def log(s):
            f.write(f'{utils.time_str()}: {s}\n')
            f.flush()

        try:
            log('Init Teamworker')
            teamworker.init()

            log('Init Shopifier')
            shopifier.init()
            rc = None

            # if the stop event hasn't been fired keep looping
            while rc != win32event.WAIT_OBJECT_0:
                log('Run Teamworker')
                try:
                    teamworker.run()
                except Exception as e:
                    log(e);

                log('Run Shopifier')
                try:
                    shopifier.run()
                except Exception as e:
                    log(e);

                # block and listen for a stop event
                log('Sleep for 5 minutes')
                rc = win32event.WaitForSingleObject(self.hWaitStop, 300000)

        except Exception as e:
            log(e)
        finally:
            log('SHUTTING DOWN')
            sys.stdout = sys.__stdout__
            f.close()

    # called when we're being shut down
    def SvcStop(self):
        # tell the SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # fire the stop event
        win32event.SetEvent(self.hWaitStop)


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(PySvc)
